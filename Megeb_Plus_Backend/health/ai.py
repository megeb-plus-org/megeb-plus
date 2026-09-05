"""
AI nutrition suggestion generator for Megeb+.

Uses today's real health data to generate one short personalized tip.
Falls back safely if Gemini is unavailable.
"""

import logging
import time
from decimal import Decimal

from django.conf import settings
from django.utils import timezone

from .models import FoodEntry, WaterLog, ExerciseLog, HealthProfile

logger = logging.getLogger(__name__)

FALLBACK_MESSAGE_LOGGED = (
    "Great job logging your meals today! Keep it up."
)

FALLBACK_MESSAGE_EMPTY = (
    "Log your first meal to get personalised nutrition insights powered by AI."
)


def _gather_today_summary(user):
    today = timezone.localdate()

    food_entries = FoodEntry.objects.filter(
        user=user,
        date=today,
    )

    calories_consumed = sum(
        (e.calories for e in food_entries),
        Decimal("0"),
    )

    protein_consumed = sum(
        (e.protein_g for e in food_entries),
        Decimal("0"),
    )

    water_ml = sum(
        (
            log.amount_ml
            for log in WaterLog.objects.filter(
                user=user,
                logged_at__date=today,
            )
        ),
        0,
    )

    activity_minutes = sum(
        (
            log.duration_minutes
            for log in ExerciseLog.objects.filter(
                user=user,
                date=today,
            )
        ),
        0,
    )

    profile = HealthProfile.objects.filter(
        user=user
    ).first()

    return {
        "calories_consumed": float(calories_consumed),
        "calorie_target": profile.calorie_target if profile else None,
        "protein_consumed": float(protein_consumed),
        "protein_target": profile.protein_target_g if profile else None,
        "water_ml": water_ml,
        "water_target_glasses": (
            profile.water_target_glasses if profile else None
        ),
        "activity_minutes": activity_minutes,
        "primary_goal": profile.health_goal if profile else None,

        # Anything meaningful logged today should allow AI generation.
        "has_logged_anything": (
            food_entries.exists()
            or water_ml > 0
            or activity_minutes > 0
        ),
    }


def _build_prompt(summary):
    calorie_line = (
        f"Calories today: {summary['calories_consumed']:.0f}"
    )

    if summary["calorie_target"]:
        calorie_line += (
            f" (target {summary['calorie_target']})"
        )

    protein_line = (
        f"Protein today: {summary['protein_consumed']:.0f}g"
    )

    if summary["protein_target"]:
        protein_line += (
            f" (target {summary['protein_target']}g)"
        )

    water_line = (
        f"Water today: {summary['water_ml']}ml"
    )

    if summary["water_target_glasses"]:
        water_line += (
            f" (target ~{summary['water_target_glasses']} glasses)"
        )

    goal_line = (
        f"User's goal: "
        f"{summary['primary_goal'] or 'general health'}"
    )

    return (
        "You are a friendly nutrition coach inside a health app.\n"
        "Based on this user's health data for today, write ONE "
        "short, warm, actionable nutrition or activity tip.\n\n"
        "Rules:\n"
        "- Maximum 25 words.\n"
        "- No medical claims.\n"
        "- No diagnosis.\n"
        "- No disclaimers.\n"
        "- Return ONLY the tip itself.\n\n"
        f"{calorie_line}\n"
        f"{protein_line}\n"
        f"{water_line}\n"
        f"Activity today: {summary['activity_minutes']} minutes\n"
        f"{goal_line}"
    )


def _clean_ai_text(text):
    """
    Clean Gemini output and keep it short enough for the dashboard.
    """

    if not text:
        return ""

    text = text.strip()

    # Remove common quotation wrapping.
    if (
        len(text) >= 2
        and text[0] == '"'
        and text[-1] == '"'
    ):
        text = text[1:-1].strip()

    # Keep maximum 25 words.
    words = text.split()

    if len(words) > 25:
        text = " ".join(words[:25]).rstrip(".,;:") + "."

    return text


def generate_ai_suggestion(user):
    """
    Generate a personalized AI suggestion for today's health data.

    Returns a safe fallback message if Gemini is unavailable.
    """

    summary = _gather_today_summary(user)

    # Don't call Gemini if the user has no data.
    if not summary["has_logged_anything"]:
        return FALLBACK_MESSAGE_EMPTY

    api_key = getattr(
        settings,
        "GEMINI_API_KEY",
        None,
    )

    if not api_key:
        logger.warning(
            "generate_ai_suggestion: GEMINI_API_KEY is not configured"
        )
        return FALLBACK_MESSAGE_LOGGED

    model = (
        getattr(settings, "GEMINI_MODEL", None)
        or "gemini-3.6-flash"
    )

    prompt = _build_prompt(summary)

    try:
        from google import genai

        client = genai.Client(
            api_key=api_key
        )

        # Gemini may temporarily return 503 when demand is high.
        for attempt in range(3):

            try:
                interaction = client.interactions.create(
                    model=model,
                    input=prompt,
                )

                text = _clean_ai_text(
                    getattr(
                        interaction,
                        "output_text",
                        "",
                    )
                )

                if text:
                    logger.info(
                        "AI suggestion generated successfully "
                        "for user_id=%s",
                        user.id,
                    )
                    return text

                logger.warning(
                    "generate_ai_suggestion: Gemini returned "
                    "empty output for user_id=%s",
                    user.id,
                )

            except Exception as exc:

                error_text = str(exc)

                logger.warning(
                    "Gemini attempt %s failed for user_id=%s: %s",
                    attempt + 1,
                    user.id,
                    error_text,
                )

                # Retry temporary service overloads.
                temporary_error = any(
                    phrase in error_text.upper()
                    for phrase in (
                        "503",
                        "UNAVAILABLE",
                        "HIGH DEMAND",
                        "RESOURCE_EXHAUSTED",
                        "429",
                    )
                )

                if temporary_error and attempt < 2:
                    time.sleep(2 ** attempt)
                    continue

                logger.exception(
                    "generate_ai_suggestion: Gemini failed "
                    "for user_id=%s",
                    user.id,
                )
                break

    except Exception:
        logger.exception(
            "generate_ai_suggestion: unexpected AI error "
            "for user_id=%s",
            user.id,
        )

    return FALLBACK_MESSAGE_LOGGED