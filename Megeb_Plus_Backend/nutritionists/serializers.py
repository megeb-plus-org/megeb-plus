from rest_framework import serializers

from .models import (
    NutritionistApplication,
    NutritionistProfile,
)


class NutritionistApplicationSerializer(
    serializers.ModelSerializer
):

    class Meta:
        model = NutritionistApplication

        fields = [
            "id",
            "user",

            # Personal information
            "full_name",
            "email",
            "phone",

            # Professional information
            "current_role",
            "specialization",
            "years_of_experience",

            # State license
            "license_number",
            "license_jurisdiction",
            "license_expiration_date",
            "license_document",

            # National credential
            "credential_type",
            "credential_number",
            "credential_document",

            # Insurance
            "insurance_provider",
            "policy_number",
            "insurance_expiration_date",
            "coverage_limit",
            "insurance_document",

            # Degree
            "degree",
            "institution",
            "field_of_study",
            "graduation_year",
            "degree_document",

            # AI verification
            "ai_status",
            "ai_score",
            "ai_result",

            # Application status
            "status",
            "rejection_reason",
            "submitted_at",
            "reviewed_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "user",

            # AI fields are controlled by backend
            "ai_status",
            "ai_score",
            "ai_result",

            # Application status is controlled by backend/admin
            "status",
            "rejection_reason",
            "submitted_at",
            "reviewed_at",
            "updated_at",
        ]
class NutritionistProfileSerializer(
    serializers.ModelSerializer
):

    full_name = serializers.CharField(
        source="user.full_name",
        read_only=True
    )

    email = serializers.EmailField(
        source="user.email",
        read_only=True
    )

    class Meta:
        model = NutritionistProfile

        fields = [
            "id",
            "user",
            "full_name",
            "email",
            "bio",
            "specialization",
            "qualification",
            "years_of_experience",
            "license_number",
            "profile_picture",
            "is_verified",
            "rating",
            "consultation_fee",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "user",
            "is_verified",
            "rating",
            "created_at",
            "updated_at",
        ]