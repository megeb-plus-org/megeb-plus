# health/utils.py
"""
Server-side mirror of utils/nutritionCalculator.ts on the mobile app.
Keep this in sync if that formula ever changes there.
"""
from decimal import Decimal
from datetime import timedelta

from django.utils import timezone

# HealthProfile.activity_level (mobile's 4-value vocabulary, see
# models.py ACTIVITY_LEVEL_CHOICES) -> the calculator's activity
# vocabulary (5 buckets — 'moderate' is simply never reached, since
# mobile only ever sends one of these 4 values).
ACTIVITY_LEVEL_MAP = {
    'mostly-sitting': 'sedentary',
    'light': 'light',
    'active': 'active',
    'very-active': 'very_active',
}

# HealthProfile.health_goal (mobile's 8-value vocabulary, see models.py
# HEALTH_GOAL_CHOICES — was primary_goal before this fix) -> the
# calculator's goal vocabulary. Only weight-loss/muscle-gain map to a
# non-default bucket; the rest (energy, healthy-eating, digestion,
# fasting-routine, support-health, other) have no calorie-adjustment
# equivalent on mobile, so they're treated as maintenance.
GOAL_MAP = {
    'weight-loss': 'lose_weight',
    'muscle-gain': 'gain_weight',
    'energy': 'maintain_weight',
    'healthy-eating': 'maintain_weight',
    'digestion': 'maintain_weight',
    'fasting-routine': 'maintain_weight',
    'support-health': 'maintain_weight',
    'other': 'maintain_weight',
}

ACTIVITY_MULTIPLIERS = {
    'sedentary': 1.2,
    'light': 1.375,
    'moderate': 1.55,
    'active': 1.725,
    'very_active': 1.9,
}


def calculate_nutrition_goals(*, sex, age, height_cm, weight_kg, activity_level, goal):
    """
    Mirrors calculateNutritionGoals() in utils/nutritionCalculator.ts exactly.

    sex: 'male' | 'female'
    activity_level / goal: already mapped via ACTIVITY_LEVEL_MAP / GOAL_MAP
    """
    weight_kg = float(weight_kg)
    height_cm = float(height_cm)
    age = float(age)

    if sex == 'male':
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + 5
    else:
        bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age - 161

    calories = bmr * ACTIVITY_MULTIPLIERS[activity_level]

    if goal == 'lose_weight':
        calories -= 300
    if goal == 'gain_weight':
        calories += 300

    calories = round(max(calories, 1200))

    protein_target_g = round(weight_kg * 1.6)
    fat_target_g = round((calories * 0.25) / 9)

    protein_calories = protein_target_g * 4
    fat_calories = fat_target_g * 9

    carbs_target_g = round(max(calories - protein_calories - fat_calories, 0) / 4)

    water_target_glasses = max(6, round(weight_kg * 0.033 / 0.25))

    return {
        'calorie_target': calories,
        'protein_target_g': protein_target_g,
        'carbs_target_g': carbs_target_g,
        'fat_target_g': fat_target_g,
        'water_target_glasses': water_target_glasses,
        'water_glass_size_ml': 250,
    }


def maybe_recalculate_targets(profile):
    """
    Recomputes and saves calorie/macro targets on a HealthProfile if enough
    data is present — mirrors the isProfileComplete check inside
    calculateAndSaveNutritionGoals() on mobile. Leaves existing targets
    untouched if the profile is incomplete or gender is 'other' (the
    Mifflin-St Jeor formula only has male/female branches).
    """
    has_required_fields = (
        profile.age is not None
        and profile.height_cm is not None
        and profile.weight_kg is not None
        and profile.gender in ('male', 'female')
        and bool(profile.activity_level)
        and bool(profile.health_goal)
    )

    if not has_required_fields:
        return profile

    mapped_activity = ACTIVITY_LEVEL_MAP.get(profile.activity_level)
    mapped_goal = GOAL_MAP.get(profile.health_goal, 'maintain_weight')

    if not mapped_activity:
        return profile

    targets = calculate_nutrition_goals(
        sex=profile.gender,
        age=profile.age,
        height_cm=profile.height_cm,
        weight_kg=profile.weight_kg,
        activity_level=mapped_activity,
        goal=mapped_goal,
    )

    for field, value in targets.items():
        setattr(profile, field, value)

    profile.save(update_fields=list(targets.keys()) + ['updated_at'])

    return profile


# --- Streaks ---
# A day "counts" toward the streak if the user met both their calorie
# and water goals that day. Change the definition in _day_goals_met()
# only — check_and_update_streak() just walks the streak forward/backward
# based on whatever that function returns, so it doesn't need to change
# if the definition does (e.g. adding an activity requirement later).

CALORIE_GOAL_TOLERANCE = 0.10  # up to 10% over calorie_target still counts as "met"


def _day_goals_met(user, date):
    """
    True if calorie AND water goals were both met for `date`.
    """
    from .models import HealthProfile, FoodEntry, WaterLog  # avoid circular import

    profile = HealthProfile.objects.filter(user=user).first()
    if not profile or not profile.calorie_target or not profile.water_target_glasses:
        return False

    calories_consumed = sum(
        (e.calories for e in FoodEntry.objects.filter(user=user, date=date)),
        Decimal("0"),
    )
    calorie_met = 0 < calories_consumed <= profile.calorie_target * Decimal(str(1 + CALORIE_GOAL_TOLERANCE))

    water_ml = sum(
        (log.amount_ml for log in WaterLog.objects.filter(user=user, logged_at__date=date)),
        0,
    )
    glasses_logged = round(water_ml / profile.water_glass_size_ml) if profile.water_glass_size_ml else 0
    water_met = glasses_logged >= profile.water_target_glasses

    return calorie_met and water_met


def check_and_update_streak(user):
    """
    Call after any food or water log is created, updated, or deleted.
    Re-evaluates *today* only (cheap — no full history walk) against the
    stored last_streak_date:

    - Today's goals newly met + last_streak_date was yesterday -> +1
    - Today's goals newly met + there's a gap (or no prior streak) -> reset to 1
    - Today's goals were met but no longer are (a log got edited/deleted) -> undo today's credit

    Note: this only re-evaluates on log changes. A user who goes fully
    inactive for a day won't have their streak reset until they next log
    something — there's no midnight cron job. Fine for now; add one later
    if streaks need to reset exactly at the day boundary for inactive users.
    """
    from .models import HealthProfile  # avoid circular import

    profile = HealthProfile.objects.filter(user=user).first()
    if not profile:
        return

    today = timezone.localdate()
    goals_met_today = _day_goals_met(user, today)

    if goals_met_today:
        if profile.last_streak_date == today:
            return  # already counted today

        if profile.last_streak_date == today - timedelta(days=1):
            profile.current_streak_days += 1
        else:
            profile.current_streak_days = 1

        profile.last_streak_date = today
        profile.longest_streak_days = max(profile.longest_streak_days, profile.current_streak_days)
        profile.save(update_fields=['current_streak_days', 'longest_streak_days', 'last_streak_date'])
    else:
        if profile.last_streak_date == today:
            profile.current_streak_days = max(profile.current_streak_days - 1, 0)
            profile.last_streak_date = (today - timedelta(days=1)) if profile.current_streak_days > 0 else None
            profile.save(update_fields=['current_streak_days', 'last_streak_date'])