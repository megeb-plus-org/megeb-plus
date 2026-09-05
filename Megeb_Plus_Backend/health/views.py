
from decimal import Decimal

from rest_framework import viewsets, permissions, status
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone

from .models import (
    HealthProfile,
    WeightLog,
    NutritionGoal,
    WaterLog,
    ExerciseLog,
    Food,
    FoodEntry,
    AISuggestion,
)
from .permissions import IsOwner
from .renderers import CamelCaseAPIMixin
from .utils import maybe_recalculate_targets, check_and_update_streak
from .ai import generate_ai_suggestion, FALLBACK_MESSAGE_EMPTY
from .serializers import (
    HealthProfileSerializer,
    NutritionGoalsSerializer,
    WeightLogSerializer,
    NutritionGoalSerializer,
    WaterLogSerializer,
    ActivityLogSerializer,
    FoodSerializer,
    FoodEntrySerializer,
    AISuggestionSerializer,
)


# ============================================================
# PROFILE -> GET/PATCH /profile/
# ============================================================

class ProfileView(CamelCaseAPIMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    USER_FIELD_MAP = {
        "name": "full_name",
        "email": "email",
        "phone": "phone",
        "profile_image": "profile_picture",
    }

    def _get_or_create_profile(self, user):
        profile, _ = HealthProfile.objects.get_or_create(user=user)
        return profile

    def _serialize(self, user, profile):
        data = {}

        for mobile_field, user_attr in self.USER_FIELD_MAP.items():
            data[mobile_field] = getattr(user, user_attr, None)

        data.update(HealthProfileSerializer(profile).data)

        data.pop("id", None)
        data.pop("user", None)

        return data

    def get(self, request):
        profile = self._get_or_create_profile(request.user)
        return Response(
            self._serialize(request.user, profile)
        )

    def patch(self, request):
        user = request.user
        profile = self._get_or_create_profile(user)

        incoming = request.data
        user_dirty = False

        for mobile_field, user_attr in self.USER_FIELD_MAP.items():
            if mobile_field in incoming:
                setattr(
                    user,
                    user_attr,
                    incoming[mobile_field],
                )
                user_dirty = True

        if user_dirty:
            user.save()

        serializer = HealthProfileSerializer(
            profile,
            data=incoming,
            partial=True,
        )

        serializer.is_valid(raise_exception=True)
        profile = serializer.save()

        maybe_recalculate_targets(profile)

        return Response(
            self._serialize(user, profile)
        )


# ============================================================
# NUTRITION GOALS -> GET /nutrition/goals/
# ============================================================

class NutritionGoalsView(CamelCaseAPIMixin, APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        profile, _ = HealthProfile.objects.get_or_create(
            user=request.user
        )

        return Response(
            NutritionGoalsSerializer(profile).data
        )


# ============================================================
# PROGRESS / WEIGHT -> /progress/weight/
# ============================================================

class WeightLogViewSet(
    CamelCaseAPIMixin,
    viewsets.ModelViewSet,
):
    serializer_class = WeightLogSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsOwner,
    ]

    def get_queryset(self):
        return WeightLog.objects.filter(
            user=self.request.user
        )

    def create(self, request, *args, **kwargs):
        date = (
            request.data.get("date")
            or timezone.localdate().isoformat()
        )

        existing = WeightLog.objects.filter(
            user=request.user,
            date=date,
        ).first()

        if existing:
            serializer = self.get_serializer(
                existing,
                data=request.data,
                partial=True,
            )

            serializer.is_valid(
                raise_exception=True
            )

            serializer.save()

            return Response(
                serializer.data,
                status=status.HTTP_200_OK,
            )

        serializer = self.get_serializer(
            data=request.data
        )

        serializer.is_valid(
            raise_exception=True
        )

        serializer.save(
            user=request.user,
            date=date,
        )

        return Response(
            serializer.data,
            status=status.HTTP_201_CREATED,
        )


# ============================================================
# NUTRITION GOAL VIEWSET
# ============================================================

class NutritionGoalViewSet(
    CamelCaseAPIMixin,
    viewsets.ModelViewSet,
):
    serializer_class = NutritionGoalSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsOwner,
    ]

    def get_queryset(self):
        return NutritionGoal.objects.filter(
            user=self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user
        )


# ============================================================
# WATER LOGS
# ============================================================

class WaterLogViewSet(
    CamelCaseAPIMixin,
    viewsets.ModelViewSet,
):
    serializer_class = WaterLogSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsOwner,
    ]

    def get_queryset(self):
        return WaterLog.objects.filter(
            user=self.request.user
        )

    def perform_create(self, serializer):
        serializer.save(
            user=self.request.user
        )

        check_and_update_streak(
            self.request.user
        )

    def perform_destroy(self, instance):
        user = instance.user

        instance.delete()

        check_and_update_streak(user)


# ============================================================
# ACTIVITY -> /activities/
# ============================================================

CALORIES_PER_MINUTE = {
    "low": 4,
    "moderate": 7,
    "high": 10,
}


class ActivityLogViewSet(
    CamelCaseAPIMixin,
    viewsets.ModelViewSet,
):
    serializer_class = ActivityLogSerializer
    permission_classes = [
        permissions.IsAuthenticated,
        IsOwner,
    ]

    def get_queryset(self):
        qs = ExerciseLog.objects.filter(
            user=self.request.user
        )

        date = self.request.query_params.get("date")

        if date:
            qs = qs.filter(date=date)

        return qs

    def _calculate_calories(
        self,
        duration_minutes,
        intensity,
    ):
        per_minute = CALORIES_PER_MINUTE.get(
            intensity,
            CALORIES_PER_MINUTE["moderate"],
        )

        return round(
            duration_minutes * per_minute
        )

    def perform_create(self, serializer):
        duration = serializer.validated_data.get(
            "duration_minutes",
            0,
        )

        intensity = serializer.validated_data.get(
            "intensity",
            "moderate",
        )

        calories = self._calculate_calories(
            duration,
            intensity,
        )

        serializer.save(
            user=self.request.user,
            calories_burned=calories,
        )

        # Activity can change today's AI advice.
        refresh_ai_suggestion_for_today(
            self.request.user
        )

        check_and_update_streak(
            self.request.user
        )

    def perform_update(self, serializer):
        duration = serializer.validated_data.get(
            "duration_minutes",
            serializer.instance.duration_minutes,
        )

        intensity = serializer.validated_data.get(
            "intensity",
            serializer.instance.intensity,
        )

        calories = self._calculate_calories(
            duration,
            intensity,
        )

        serializer.save(
            calories_burned=calories
        )

        refresh_ai_suggestion_for_today(
            self.request.user
        )

        check_and_update_streak(
            self.request.user
        )

    def perform_destroy(self, instance):
        user = instance.user

        instance.delete()

        refresh_ai_suggestion_for_today(user)
        check_and_update_streak(user)

    @action(
        detail=False,
        methods=["get"],
        url_path="summary",
    )
    def summary(self, request):
        date = (
            request.query_params.get("date")
            or timezone.localdate().isoformat()
        )

        qs = ExerciseLog.objects.filter(
            user=request.user,
            date=date,
        )

        calories_burned = sum(
            (
                e.calories_burned or Decimal("0")
                for e in qs
            ),
            Decimal("0"),
        )

        active_minutes = sum(
            (
                e.duration_minutes
                for e in qs
            ),
            0,
        )

        return Response({
            "calories_burned": calories_burned,
            "active_minutes": active_minutes,
            "activities_count": qs.count(),
        })


# ============================================================
# FOOD CATALOG
# ============================================================

class FoodViewSet(
    CamelCaseAPIMixin,
    viewsets.ReadOnlyModelViewSet,
):
    queryset = Food.objects.all()
    serializer_class = FoodSerializer
    permission_classes = [
        permissions.IsAuthenticated
    ]

    @action(
        detail=False,
        methods=["get"],
        url_path="search",
    )
    def search(self, request):
        query = (
            request.query_params.get("q")
            or ""
        ).strip()

        qs = self.get_queryset()

        if query:
            from django.db.models import Q

            qs = qs.filter(
                Q(name__icontains=query)
                | Q(category__icontains=query)
            )

        return Response(
            FoodSerializer(
                qs,
                many=True,
            ).data
        )

    @action(
        detail=False,
        methods=["post"],
        url_path="nutrition",
    )
    def nutrition(self, request):
        food_id = request.data.get(
            "food_id"
        )

        grams = request.data.get(
            "grams"
        )

        if not food_id:
            raise ValidationError({
                "food_id": "This field is required."
            })

        try:
            grams = Decimal(
                str(grams)
            )
        except Exception:
            raise ValidationError({
                "grams": "Must be a positive number."
            })

        if grams <= 0:
            raise ValidationError({
                "grams": "Must be greater than zero."
            })

        try:
            food = Food.objects.get(
                pk=food_id
            )
        except Food.DoesNotExist:
            raise ValidationError({
                "food_id": "No food with this id."
            })

        ratio = grams / Decimal("100")

        return Response({
            "calories": round(
                food.calories_per_100g * ratio,
                2,
            ),
            "protein_g": round(
                food.protein_g * ratio,
                2,
            ),
            "carbs_g": round(
                food.carbs_g * ratio,
                2,
            ),
            "fat_g": round(
                food.fat_g * ratio,
                2,
            ),
            "fiber_g": round(
                food.fiber_g * ratio,
                2,
            ),
        })


# ============================================================
# FOOD DIARY
# ============================================================

MEAL_TYPES = [
    "breakfast",
    "lunch",
    "dinner",
    "snacks",
]


def _compute_food_entry_nutrition(
    food,
    grams,
):
    """
    Calculate nutrition from the food catalog.
    The server owns these values.
    """

    ratio = (
        Decimal(str(grams))
        / Decimal("100")
    )

    return {
        "food_name": food.name,
        "calories": round(
            food.calories_per_100g * ratio,
            2,
        ),
        "protein_g": round(
            food.protein_g * ratio,
            2,
        ),
        "carbs_g": round(
            food.carbs_g * ratio,
            2,
        ),
        "fat_g": round(
            food.fat_g * ratio,
            2,
        ),
        "fiber_g": round(
            food.fiber_g * ratio,
            2,
        ),
    }


def _serialize_meal_group(
    meal_type,
    entries,
):
    entries = list(entries)

    total_calories = sum(
        (
            e.calories
            for e in entries
        ),
        Decimal("0"),
    )

    return {
        "id": meal_type,
        "type": meal_type,
        "foods": FoodEntrySerializer(
            entries,
            many=True,
        ).data,
        "calories": total_calories,
    }


class FoodDiaryViewSet(
    CamelCaseAPIMixin,
    viewsets.ViewSet,
):
    """
    GET    /food-diary/
    POST   /food-diary/
    PATCH  /food-diary/{entry_id}/
    DELETE /food-diary/{entry_id}/
    GET    /food-diary/nutrition/
    """

    permission_classes = [
        permissions.IsAuthenticated
    ]

    def _entries_for_date(
        self,
        user,
        date,
    ):
        return FoodEntry.objects.filter(
            user=user,
            date=date,
        )

    def list(self, request):
        date = (
            request.query_params.get("date")
            or timezone.localdate().isoformat()
        )

        entries = self._entries_for_date(
            request.user,
            date,
        )

        groups = [
            _serialize_meal_group(
                meal_type,
                entries.filter(
                    meal_type=meal_type
                ),
            )
            for meal_type in MEAL_TYPES
        ]

        return Response(groups)

    def create(self, request):
        data = request.data

        date = (
            data.get("date")
            or timezone.localdate().isoformat()
        )

        meal_type = data.get(
            "meal_type"
        )

        food_id = data.get(
            "food_id"
        )

        grams = data.get(
            "grams"
        )

        portion = data.get(
            "portion",
            "",
        )

        if meal_type not in MEAL_TYPES:
            raise ValidationError({
                "meal_type":
                    f"Must be one of {MEAL_TYPES}."
            })

        if not food_id:
            raise ValidationError({
                "food_id":
                    "This field is required."
            })

        try:
            grams = Decimal(
                str(grams)
            )

            assert grams > 0

        except Exception:
            raise ValidationError({
                "grams":
                    "Must be a positive number."
            })

        try:
            food = Food.objects.get(
                pk=food_id
            )

        except Food.DoesNotExist:
            raise ValidationError({
                "food_id":
                    "No food with this id."
            })

        nutrition = (
            _compute_food_entry_nutrition(
                food,
                grams,
            )
        )

        FoodEntry.objects.create(
            user=request.user,
            food=food,
            meal_type=meal_type,
            date=date,
            portion_label=portion,
            grams=grams,
            **nutrition,
        )

        # Refresh AI after a new meal.
        refresh_ai_suggestion_for_today(
            request.user
        )

        check_and_update_streak(
            request.user
        )

        entries = (
            self._entries_for_date(
                request.user,
                date,
            )
            .filter(
                meal_type=meal_type
            )
        )

        return Response(
            _serialize_meal_group(
                meal_type,
                entries,
            ),
            status=status.HTTP_201_CREATED,
        )

    def partial_update(
        self,
        request,
        pk=None,
    ):
        try:
            entry = FoodEntry.objects.get(
                pk=pk,
                user=request.user,
            )

        except FoodEntry.DoesNotExist:
            return Response(
                status=status.HTTP_404_NOT_FOUND
            )

        data = request.data

        if (
            "grams" in data
            or "portion" in data
        ):
            grams = data.get(
                "grams",
                entry.grams,
            )

            try:
                grams = Decimal(
                    str(grams)
                )

                assert grams > 0

            except Exception:
                raise ValidationError({
                    "grams":
                        "Must be a positive number."
                })

            entry.grams = grams

            if entry.food:
                nutrition = (
                    _compute_food_entry_nutrition(
                        entry.food,
                        grams,
                    )
                )

                for field, value in nutrition.items():
                    setattr(
                        entry,
                        field,
                        value,
                    )

        if "portion" in data:
            entry.portion_label = data[
                "portion"
            ]

        if "meal_type" in data:
            if data["meal_type"] not in MEAL_TYPES:
                raise ValidationError({
                    "meal_type":
                        f"Must be one of {MEAL_TYPES}."
                })

            entry.meal_type = data[
                "meal_type"
            ]

        entry.save()

        refresh_ai_suggestion_for_today(
            request.user
        )

        check_and_update_streak(
            request.user
        )

        entries = (
            self._entries_for_date(
                request.user,
                entry.date,
            )
            .filter(
                meal_type=entry.meal_type
            )
        )

        return Response(
            _serialize_meal_group(
                entry.meal_type,
                entries,
            )
        )

    def destroy(
        self,
        request,
        pk=None,
    ):
        try:
            entry = FoodEntry.objects.get(
                pk=pk,
                user=request.user,
            )

        except FoodEntry.DoesNotExist:
            return Response(
                status=status.HTTP_404_NOT_FOUND
            )

        user = entry.user

        entry.delete()

        refresh_ai_suggestion_for_today(
            user
        )

        check_and_update_streak(user)

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )

    @action(
        detail=False,
        methods=["get"],
        url_path="nutrition",
    )
    def nutrition(self, request):
        date = (
            request.query_params.get("date")
            or timezone.localdate().isoformat()
        )

        entries = self._entries_for_date(
            request.user,
            date,
        )

        return Response({
            "calories": sum(
                (
                    e.calories
                    for e in entries
                ),
                Decimal("0"),
            ),
            "protein_g": sum(
                (
                    e.protein_g
                    for e in entries
                ),
                Decimal("0"),
            ),
            "carbs_g": sum(
                (
                    e.carbs_g
                    for e in entries
                ),
                Decimal("0"),
            ),
            "fat_g": sum(
                (
                    e.fat_g
                    for e in entries
                ),
                Decimal("0"),
            ),
            "fiber_g": sum(
                (
                    e.fiber_g
                    for e in entries
                ),
                Decimal("0"),
            ),
        })


# ============================================================
# AI SUGGESTION
# ============================================================

def refresh_ai_suggestion_for_today(user):
    """
    Generate and cache today's AI suggestion.
    """

    today = timezone.localdate()

    try:
        message = generate_ai_suggestion(user)

        AISuggestion.objects.update_or_create(
            user=user,
            date=today,
            defaults={
                "message": message,
            },
        )

        return message

    except Exception as e:
        import logging

        logging.exception(
            "AI suggestion refresh failed "
            "for user %s: %s",
            user.id,
            e,
        )

        return None


class AISuggestionView(
    CamelCaseAPIMixin,
    APIView,
):
    """
    Returns today's AI-generated nutrition tip.

    Cached per user per day.

    ?refresh=true forces a new generation.
    """

    permission_classes = [
        permissions.IsAuthenticated
    ]

    def get(self, request):
        today = timezone.localdate()

        force_refresh = (
            request.query_params.get(
                "refresh"
            )
            == "true"
        )

        if not force_refresh:
            existing = AISuggestion.objects.filter(
                user=request.user,
                date=today,
            ).first()

            if (
                existing
                and existing.message
                != FALLBACK_MESSAGE_EMPTY
            ):
                return Response(
                    AISuggestionSerializer(
                        existing
                    ).data
                )

        message = generate_ai_suggestion(
            request.user
        )

        suggestion, _ = (
            AISuggestion.objects.update_or_create(
                user=request.user,
                date=today,
                defaults={
                    "message": message,
                },
            )
        )

        return Response(
            AISuggestionSerializer(
                suggestion
            ).data
        )


# ============================================================
# DASHBOARD
# ============================================================

class DashboardView(
    CamelCaseAPIMixin,
    APIView,
):
    """
    Aggregated health dashboard.
    """

    permission_classes = [
        permissions.IsAuthenticated
    ]

    def get(self, request):
        user = request.user

        today = timezone.localdate()

        profile = HealthProfile.objects.filter(
            user=user
        ).first()

        # ----------------------------------------------------
        # FOOD
        # ----------------------------------------------------

        food_entries = FoodEntry.objects.filter(
            user=user,
            date=today,
        )

        calories_consumed = sum(
            (
                e.calories
                for e in food_entries
            ),
            Decimal("0"),
        )

        protein_consumed = sum(
            (
                e.protein_g
                for e in food_entries
            ),
            Decimal("0"),
        )

        carbs_consumed = sum(
            (
                e.carbs_g
                for e in food_entries
            ),
            Decimal("0"),
        )

        fat_consumed = sum(
            (
                e.fat_g
                for e in food_entries
            ),
            Decimal("0"),
        )

        # ----------------------------------------------------
        # WATER
        # ----------------------------------------------------

        water_logs_today = WaterLog.objects.filter(
            user=user,
            logged_at__date=today,
        )

        water_ml = sum(
            (
                log.amount_ml
                for log in water_logs_today
            ),
            0,
        )

        glass_size = (
            profile.water_glass_size_ml
            if profile
            else 250
        )

        glasses_logged = (
            round(
                water_ml / glass_size
            )
            if glass_size
            else 0
        )

        water_target = (
            profile.water_target_glasses
            if profile
            else None
        )

        # ----------------------------------------------------
        # ACTIVITY
        # ----------------------------------------------------

        exercise_today = ExerciseLog.objects.filter(
            user=user,
            date=today,
        )

        calories_burned = sum(
            (
                e.calories_burned
                or Decimal("0")
                for e in exercise_today
            ),
            Decimal("0"),
        )

        # ----------------------------------------------------
        # AI SUGGESTION
        # ----------------------------------------------------

        ai_suggestion = AISuggestion.objects.filter(
            user=user,
            date=today,
        ).first()

        # If there is no cached suggestion,
        # generate one now.
        #
        # Also regenerate if the cached message is the
        # "log your first meal" placeholder but the user
        # now has food logged.
        if (
            not ai_suggestion
            or (
                ai_suggestion.message
                == FALLBACK_MESSAGE_EMPTY
                and food_entries.exists()
            )
        ):
            refresh_ai_suggestion_for_today(
                user
            )

            ai_suggestion = AISuggestion.objects.filter(
                user=user,
                date=today,
            ).first()

        # ----------------------------------------------------
        # CALORIE TARGET
        # ----------------------------------------------------

        calorie_target = (
            profile.calorie_target
            if profile
            else None
        )

        # ----------------------------------------------------
        # RESPONSE
        # ----------------------------------------------------

        return Response({
            "user_name": (
                getattr(
                    user,
                    "full_name",
                    "",
                )
                or ""
            ),

            "calories": {
                "consumed": calories_consumed,
                "burned": calories_burned,
                "net": (
                    calories_consumed
                    - calories_burned
                ),
                "target": calorie_target or 0,
                "target_source": (
                    "calculated"
                    if calorie_target
                    else "default"
                ),
            },

            "macros": {
                "protein": {
                    "consumed": protein_consumed,
                    "target": (
                        profile.protein_target_g
                        if profile
                        else 0
                    ),
                },

                "carbs": {
                    "consumed": carbs_consumed,
                    "target": (
                        profile.carbs_target_g
                        if profile
                        else 0
                    ),
                },

                "fats": {
                    "consumed": fat_consumed,
                    "target": (
                        profile.fat_target_g
                        if profile
                        else 0
                    ),
                },
            },

            "hydration": {
                "glasses_consumed": glasses_logged,
                "glasses_target": (
                    water_target or 0
                ),
                "glass_size_ml": glass_size,
            },

            "streak": (
                {
                    "days":
                        profile.current_streak_days
                }
                if profile
                else None
            ),

            "ai_suggestion": (
                {
                    "message":
                        ai_suggestion.message
                }
                if ai_suggestion
                else None
            ),

            "upcoming_appointment": None,
        })

