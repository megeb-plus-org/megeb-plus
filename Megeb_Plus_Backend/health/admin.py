from django.contrib import admin
from .models import (
    HealthProfile, WeightLog, NutritionGoal, WaterLog, ExerciseLog,
    Food, FoodEntry, AISuggestion,
)


@admin.register(HealthProfile)
class HealthProfileAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'health_goal', 'activity_level', 'calorie_target',
        'current_streak_days', 'longest_streak_days', 'updated_at',
    )
    list_filter = ('health_goal', 'activity_level', 'gender')
    search_fields = ('user__email', 'user__full_name')


@admin.register(WeightLog)
class WeightLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'weight_kg', 'date')
    list_filter = ('date',)
    search_fields = ('user__email',)


@admin.register(NutritionGoal)
class NutritionGoalAdmin(admin.ModelAdmin):
    list_display = ('user', 'goal_type', 'status', 'target_date')
    list_filter = ('goal_type', 'status')
    search_fields = ('user__email',)


@admin.register(WaterLog)
class WaterLogAdmin(admin.ModelAdmin):
    list_display = ('user', 'amount_ml', 'logged_at')
    list_filter = ('logged_at',)
    search_fields = ('user__email',)


@admin.register(ExerciseLog)
class ExerciseLogAdmin(admin.ModelAdmin):
    list_display = (
        'user', 'activity_type', 'intensity', 'duration_minutes',
        'calories_burned', 'date',
    )
    list_filter = ('intensity', 'activity_type', 'date')
    search_fields = ('user__email',)


@admin.register(Food)
class FoodAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'calories_per_100g', 'protein_g', 'carbs_g', 'fat_g')
    list_filter = ('category',)
    search_fields = ('name', 'category')


@admin.register(FoodEntry)
class FoodEntryAdmin(admin.ModelAdmin):
    list_display = ('user', 'food_name', 'meal_type', 'grams', 'calories', 'date')
    list_filter = ('meal_type', 'date')
    search_fields = ('user__email', 'food_name')


@admin.register(AISuggestion)
class AISuggestionAdmin(admin.ModelAdmin):
    list_display = ('user', 'date', 'created_at')
    list_filter = ('date',)
    search_fields = ('user__email',)