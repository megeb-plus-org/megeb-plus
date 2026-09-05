from rest_framework import serializers
from .models import (
    HealthProfile, WeightLog, NutritionGoal, WaterLog, ExerciseLog,
    Food, FoodEntry, AISuggestion,
)


# ============================================================
# PROFILE
# ============================================================
#
# Mobile's GET/PATCH /profile/ is ONE composite object spanning the
# User account fields (name/email/phone) and the HealthProfile
# fields. This serializer only covers the HealthProfile half —
# ProfileSerializer in views.py's ProfileView merges it with the User
# fields, since accounts/models.py wasn't provided to this pass. See
# MIGRATION_NOTES.md for the assumption made about User's field names
# (full_name/email/phone) — flag it if those are wrong and it's a
# one-line fix.
#
# Field names below are plain snake_case and rely on the
# CamelCaseAPIMixin (renderers.py) applied in views.py to convert
# to/from camelCase automatically EXCEPT for `height` and `weight`,
# which need an explicit `source=` because the mobile names aren't
# just a casing change of height_cm/weight_kg.

class HealthProfileSerializer(serializers.ModelSerializer):
    height = serializers.DecimalField(
        source='height_cm', max_digits=5, decimal_places=2,
        required=False, allow_null=True,
    )
    weight = serializers.DecimalField(
        source='weight_kg', max_digits=5, decimal_places=2,
        required=False, allow_null=True,
    )

    class Meta:
        model = HealthProfile
        fields = [
            'id', 'user', 'age', 'gender', 'height', 'weight',
            'activity_level', 'medical_conditions', 'allergies',
            'other_allergy', 'diet_preference',
            'meals_per_day', 'fasting_preference',
            'health_goal', 'other_health_goal',
            'calorie_target', 'protein_target_g', 'carbs_target_g',
            'fat_target_g', 'water_target_glasses', 'water_glass_size_ml',
            'current_streak_days', 'longest_streak_days', 'last_streak_date',
            'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'user', 'created_at', 'updated_at',
            'calorie_target', 'protein_target_g', 'carbs_target_g',
            'fat_target_g', 'water_target_glasses', 'water_glass_size_ml',
            'current_streak_days', 'longest_streak_days', 'last_streak_date',
        ]


# ============================================================
# NUTRITION GOALS  (GET /nutrition/goals/)
# ============================================================
# All 6 fields here are auto-camelCased correctly (calorie_target ->
# calorieTarget, protein_target_g -> proteinTargetG, etc.) so no
# explicit source= needed.

class NutritionGoalsSerializer(serializers.ModelSerializer):
    class Meta:
        model = HealthProfile
        fields = [
            'calorie_target', 'protein_target_g', 'carbs_target_g',
            'fat_target_g', 'water_target_glasses', 'water_glass_size_ml',
        ]


class WeightLogSerializer(serializers.ModelSerializer):
    # Mobile's WeightEntry type is {date, weight} — "weight" not
    # "weightKg", so an explicit source= is needed here too.
    weight = serializers.DecimalField(
        source='weight_kg', max_digits=6, decimal_places=2,
    )

    class Meta:
        model = WeightLog
        fields = ['id', 'date', 'weight']


class NutritionGoalSerializer(serializers.ModelSerializer):
    class Meta:
        model = NutritionGoal
        fields = [
            'id', 'user', 'goal_type', 'target_weight_kg',
            'target_date', 'status', 'created_at',
        ]
        read_only_fields = ['id', 'user', 'created_at']


class WaterLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = WaterLog
        fields = ['id', 'user', 'amount_ml', 'logged_at']
        read_only_fields = ['id', 'user', 'logged_at']


# ============================================================
# ACTIVITY  (mobile: /activities/)
# ============================================================
# Mobile's LogActivityData/LoggedActivity types use "activity" and
# "duration", not "activityType"/"durationMinutes" — real name
# mismatches, not just casing, so both need explicit source=.

class ActivityLogSerializer(serializers.ModelSerializer):
    activity = serializers.CharField(source='activity_type', max_length=100)
    duration = serializers.IntegerField(source='duration_minutes', min_value=1)

    class Meta:
        model = ExerciseLog
        fields = [
            'id', 'date', 'activity', 'intensity', 'duration',
            'calories_burned',
        ]
        # calories_burned is computed server-side in the view
        # (from duration_minutes + intensity), never client-supplied.
        read_only_fields = ['id', 'calories_burned']


# ============================================================
# FOOD CATALOG  (mobile: /foods/)
# ============================================================

class FoodSerializer(serializers.ModelSerializer):
    class Meta:
        model = Food
        fields = [
            'id', 'name', 'category',
            'calories_per_100g', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g',
        ]


# ============================================================
# FOOD DIARY  (mobile: /food-diary/)
# ============================================================
# Mobile's FoodEntry type uses "foodId" and "portion", not the
# model's "food" (FK) / "portion_label" — explicit source= for both.
# Everything else (food_name -> foodName, protein_g -> proteinG, ...)
# is handled by the CamelCaseAPIMixin automatically.

class FoodEntrySerializer(serializers.ModelSerializer):
    food_id = serializers.PrimaryKeyRelatedField(
        source='food', queryset=Food.objects.all(),
        required=False, allow_null=True,
    )
    portion = serializers.CharField(
        source='portion_label', required=False, allow_blank=True, max_length=100,
    )

    class Meta:
        model = FoodEntry
        fields = [
            'id', 'food_id', 'food_name', 'meal_type', 'date',
            'portion', 'grams',
            'calories', 'protein_g', 'carbs_g', 'fat_g', 'fiber_g',
            'logged_at',
        ]
        # calories/protein_g/carbs_g/fat_g/fiber_g/food_name are all
        # computed server-side from the Food catalog row + grams in
        # FoodDiaryViewSet.perform_create — never client-supplied, so
        # historical entries stay correct even if the Food catalog
        # changes later.
        read_only_fields = [
            'id', 'food_name', 'calories', 'protein_g', 'carbs_g',
            'fat_g', 'fiber_g', 'logged_at',
        ]


class AISuggestionSerializer(serializers.ModelSerializer):
    class Meta:
        model = AISuggestion
        fields = ['id', 'message', 'date', 'created_at']
        read_only_fields = fields
