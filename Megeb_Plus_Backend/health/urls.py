from django.urls import path
from rest_framework.routers import DefaultRouter
from .views import (
    ProfileView, NutritionGoalsView,
    WeightLogViewSet, NutritionGoalViewSet, WaterLogViewSet,
    ActivityLogViewSet, FoodViewSet, FoodDiaryViewSet,
    AISuggestionView, DashboardView,
)

router = DefaultRouter()
router.register(r'progress/weight', WeightLogViewSet, basename='weight-log')
router.register(r'nutrition-goals-tracker', NutritionGoalViewSet, basename='nutrition-goal')
router.register(r'water-logs', WaterLogViewSet, basename='water-log')
router.register(r'activities', ActivityLogViewSet, basename='activity')
router.register(r'foods', FoodViewSet, basename='food')
router.register(r'food-diary', FoodDiaryViewSet, basename='food-diary')

urlpatterns = router.urls + [
    path('profile/', ProfileView.as_view(), name='profile'),
    path('nutrition/goals/', NutritionGoalsView.as_view(), name='nutrition-goals'),
    path('ai-suggestion/', AISuggestionView.as_view(), name='ai-suggestion'),
    path('dashboard/', DashboardView.as_view(), name='dashboard'),
]
