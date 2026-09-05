from django.contrib import admin
from .models import NutritionistApplication, NutritionistProfile


@admin.register(NutritionistApplication)
class NutritionistApplicationAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "full_name",
        "email",
        "phone",
        "license_number",
        "status",
        "ai_status",
        "ai_score",
        "submitted_at",
        "updated_at",
    )

    list_filter = (
        "status",
        "ai_status",
        "submitted_at",
    )

    search_fields = (
        "full_name",
        "email",
        "phone",
        "license_number",
        "user__full_name",
        "user__email",
        "user__phone",
    )

    readonly_fields = (
        "submitted_at",
        "updated_at",
        "reviewed_at",
        "ai_result",
        "ai_score",
    )

    ordering = ("-submitted_at",)


@admin.register(NutritionistProfile)
class NutritionistProfileAdmin(admin.ModelAdmin):

    list_display = (
        "id",
        "user",
        "specialization",
        "years_of_experience",
        "license_number",
        "is_verified",
        "rating",
        "consultation_fee",
        "created_at",
    )

    list_filter = (
        "is_verified",
        "specialization",
    )

    search_fields = (
        "user__full_name",
        "user__email",
        "user__phone",
        "license_number",
        "specialization",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)