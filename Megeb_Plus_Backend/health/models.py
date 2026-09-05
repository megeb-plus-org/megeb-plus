# models.py
from django.db import models
from django.utils import timezone
from accounts.models import User


class HealthProfile(models.Model):
    # --- Choice vocabularies ---
    # These match the mobile app's actual onboarding screens exactly
    # (types/profile.ts) — mobile is the source of truth, not a guess.
    # If the mobile onboarding UI ever changes these value sets, update
    # here AND in health/utils.py's ACTIVITY_LEVEL_MAP / GOAL_MAP.

    GENDER_CHOICES = [
        ('female', 'Female'),
        ('male', 'Male'),
        ('private', 'Prefer not to say'),
    ]

    # types/profile.ts ActivityLevel
    ACTIVITY_LEVEL_CHOICES = [
        ('mostly-sitting', 'Mostly Sitting'),
        ('light', 'Light Activity'),
        ('active', 'Active'),
        ('very-active', 'Very Active'),
    ]

    # types/profile.ts FastingPreference
    FASTING_PREFERENCE_CHOICES = [
        ('none', 'No Fasting'),
        ('sometimes', 'Sometimes'),
        ('regularly', 'Regularly'),
        ('religious', 'Religious Fasting'),
    ]

    # types/profile.ts HealthGoal (was PRIMARY_GOAL_CHOICES / primary_goal
    # before this fix — renamed to health_goal to match the mobile field
    # name exactly once camelCased)
    HEALTH_GOAL_CHOICES = [
        ('weight-loss', 'Weight Loss'),
        ('muscle-gain', 'Muscle Gain'),
        ('energy', 'More Energy'),
        ('healthy-eating', 'Healthy Eating'),
        ('digestion', 'Digestion'),
        ('fasting-routine', 'Fasting Routine'),
        ('support-health', 'Support a Health Condition'),
        ('other', 'Other'),
    ]

    # types/profile.ts DietPreference
    DIET_PREFERENCE_CHOICES = [
        ('none', 'No Preference'),
        ('vegetarian', 'Vegetarian'),
        ('vegan', 'Vegan'),
        ('halal', 'Halal'),
        ('other', 'Other'),
    ]

    user = models.OneToOneField(
        User,
        on_delete=models.CASCADE,
        related_name="health_profile"
    )

    age = models.PositiveIntegerField(null=True, blank=True)
    gender = models.CharField(
        max_length=20,
        choices=GENDER_CHOICES,
        null=True,
        blank=True
    )

    # Exposed to mobile as "height" / "weight" (not heightCm/weightKg) —
    # see height/weight source-aliased fields in serializers.py.
    height_cm = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )
    weight_kg = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        null=True,
        blank=True
    )

    activity_level = models.CharField(
        max_length=20,
        choices=ACTIVITY_LEVEL_CHOICES,
        null=True,
        blank=True
    )

    medical_conditions = models.JSONField(
        default=list,
        blank=True
    )

    allergies = models.JSONField(
        default=list,
        blank=True
    )

    # Free-text field paired with allergies, matches mobile's
    # otherAllergy (used when the user picks "other" in the allergy list).
    other_allergy = models.CharField(
        max_length=255,
        blank=True,
        default=''
    )

    # Replaces the old `dietary_preferences` JSONField (a list) — mobile's
    # onboarding only ever collects ONE diet preference, not a list.
    diet_preference = models.CharField(
        max_length=20,
        choices=DIET_PREFERENCE_CHOICES,
        null=True,
        blank=True
    )

    # --- Lifestyle / nutrition / goal fields ---
    # mealsPerDay on mobile is a free-form string (e.g. "3", "4-5"), not
    # always numeric — kept as CharField per the mobile contract rather
    # than guessing it's always an integer.
    meals_per_day = models.CharField(
        max_length=10,
        null=True,
        blank=True,
        help_text="From lifestyle screen. Free text on mobile (e.g. '3', '4-5'), not guaranteed numeric."
    )
    fasting_preference = models.CharField(
        max_length=20,
        choices=FASTING_PREFERENCE_CHOICES,
        null=True,
        blank=True,
        help_text="From nutrition screen"
    )
    health_goal = models.CharField(
        max_length=30,
        choices=HEALTH_GOAL_CHOICES,
        null=True,
        blank=True,
        help_text="From health-goals screen. Was `primary_goal` — renamed to match mobile's `healthGoal` field."
    )
    # Free-text field paired with health_goal, matches mobile's
    # otherHealthGoal (used when the user picks "other" as their goal).
    other_health_goal = models.CharField(
        max_length=255,
        blank=True,
        default=''
    )

    # --- Calculated nutrition targets ---
    # Auto-computed server-side (see health/utils.py) whenever the profile
    # has enough data — mirrors calculateAndSaveNutritionGoals() on mobile.
    # Never set these directly from client input.
    calorie_target = models.PositiveIntegerField(null=True, blank=True)
    protein_target_g = models.PositiveIntegerField(null=True, blank=True)
    carbs_target_g = models.PositiveIntegerField(null=True, blank=True)
    fat_target_g = models.PositiveIntegerField(null=True, blank=True)
    water_target_glasses = models.PositiveIntegerField(null=True, blank=True)
    water_glass_size_ml = models.PositiveIntegerField(default=250)

    # --- Streaks ---
    # Maintained server-side by health/utils.check_and_update_streak(),
    # called whenever a food or water log is created/updated/deleted.
    # Never set these directly from client input.
    current_streak_days = models.PositiveIntegerField(default=0)
    longest_streak_days = models.PositiveIntegerField(default=0)
    last_streak_date = models.DateField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"Health Profile - {self.user.email}"


class WeightLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="weight_logs"
    )
    weight_kg = models.DecimalField(max_digits=6, decimal_places=2)

    # The calendar day this weight applies to. Distinct from logged_at
    # (server timestamp) so a user can log for "today" specifically and
    # re-logging the same day updates the existing entry rather than
    # creating a duplicate — see WeightLogViewSet.create().
    date = models.DateField(default=timezone.localdate)

    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'date'],
                name='unique_weight_log_per_user_per_date'
            )
        ]

    def __str__(self):
        return f"{self.user.email} - {self.weight_kg}kg @ {self.date}"


class NutritionGoal(models.Model):
    GOAL_TYPE_CHOICES = [
        ('lose_weight', 'Lose Weight'),
        ('gain_weight', 'Gain Weight'),
        ('maintain_weight', 'Maintain Weight'),
        ('build_muscle', 'Build Muscle'),
        ('improve_health', 'Improve Health'),
    ]

    STATUS_CHOICES = [
        ('active', 'Active'),
        ('completed', 'Completed'),
        ('abandoned', 'Abandoned'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="nutrition_goals"
    )
    goal_type = models.CharField(max_length=30, choices=GOAL_TYPE_CHOICES)
    target_weight_kg = models.DecimalField(max_digits=6, decimal_places=2, null=True, blank=True)
    target_date = models.DateField(null=True, blank=True)
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.user.email} - {self.goal_type} ({self.status})"


class WaterLog(models.Model):
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="water_logs"
    )
    amount_ml = models.PositiveIntegerField()
    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-logged_at']

    def __str__(self):
        return f"{self.user.email} - {self.amount_ml}ml @ {self.logged_at}"


class ExerciseLog(models.Model):
    """
    Exposed to mobile as /activities/ (ActivityLogViewSet in views.py).
    Model/table names are unchanged (no destructive rename), only the
    URL and JSON field names are aliased to match mobile — see
    ActivityLogSerializer in serializers.py.
    """
    INTENSITY_CHOICES = [
        ('low', 'Low'),
        ('moderate', 'Moderate'),
        ('high', 'High'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="exercise_logs"
    )
    # Exposed to mobile as "activity" (not "activityType") — see
    # ActivityLogSerializer.
    activity_type = models.CharField(max_length=100)
    intensity = models.CharField(
        max_length=10,
        choices=INTENSITY_CHOICES,
        default='moderate'
    )
    # Exposed to mobile as "duration" (not "durationMinutes") — see
    # ActivityLogSerializer.
    duration_minutes = models.PositiveIntegerField()

    # Always server-calculated from duration_minutes + intensity
    # (see CALORIES_PER_MINUTE in views.py) — never trust a client value.
    calories_burned = models.DecimalField(max_digits=8, decimal_places=2, null=True, blank=True)

    # The day this activity is logged against — lets a user log for
    # today or a recent past day, distinct from logged_at (server timestamp).
    date = models.DateField(default=timezone.localdate)

    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', '-logged_at']

    def __str__(self):
        return f"{self.user.email} - {self.activity_type} ({self.duration_minutes} min) @ {self.date}"


class Food(models.Model):
    name = models.CharField(max_length=150)
    category = models.CharField(max_length=100, null=True, blank=True)

    calories_per_100g = models.DecimalField(max_digits=7, decimal_places=2)
    protein_g = models.DecimalField(max_digits=6, decimal_places=2)
    carbs_g = models.DecimalField(max_digits=6, decimal_places=2)
    fat_g = models.DecimalField(max_digits=6, decimal_places=2)
    fiber_g = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class FoodEntry(models.Model):
    MEAL_TYPE_CHOICES = [
        ('breakfast', 'Breakfast'),
        ('lunch', 'Lunch'),
        ('dinner', 'Dinner'),
        ('snacks', 'Snacks'),
    ]

    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="food_entries"
    )

    # Nullable: lets an entry survive even if the underlying Food
    # is later edited/removed, and supports future "custom food" entries
    # that aren't tied to a catalog row. Exposed to mobile as "foodId".
    food = models.ForeignKey(
        Food,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="entries"
    )

    food_name = models.CharField(max_length=150)
    meal_type = models.CharField(max_length=20, choices=MEAL_TYPE_CHOICES)
    date = models.DateField()

    # Exposed to mobile as "portion" (not "portionLabel").
    portion_label = models.CharField(max_length=100, blank=True)
    grams = models.DecimalField(max_digits=7, decimal_places=2)

    # Snapshot of nutrition at the time of logging (grams * food ratios),
    # computed server-side in FoodDiaryViewSet.perform_create — never
    # client-supplied — so historical entries never change if the Food
    # catalog is edited later.
    calories = models.DecimalField(max_digits=7, decimal_places=2)
    protein_g = models.DecimalField(max_digits=6, decimal_places=2)
    carbs_g = models.DecimalField(max_digits=6, decimal_places=2)
    fat_g = models.DecimalField(max_digits=6, decimal_places=2)
    fiber_g = models.DecimalField(max_digits=6, decimal_places=2, default=0)

    logged_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date', 'logged_at']

    def __str__(self):
        return f"{self.user.email} - {self.food_name} ({self.meal_type}) @ {self.date}"


class AISuggestion(models.Model):
    """
    A cached, LLM-generated tip for a user's dashboard.
    One per user per day — see health/ai.py for generation logic
    and AISuggestionView for the cache/refresh behavior.
    """
    user = models.ForeignKey(
        User,
        on_delete=models.CASCADE,
        related_name="ai_suggestions"
    )
    date = models.DateField(default=timezone.localdate)
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-date']
        constraints = [
            models.UniqueConstraint(
                fields=['user', 'date'],
                name='unique_ai_suggestion_per_user_per_date'
            )
        ]

    def __str__(self):
        return f"{self.user.email} - AI suggestion @ {self.date}"
