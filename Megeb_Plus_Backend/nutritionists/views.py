from django.utils import timezone
from rest_framework import status
from rest_framework.permissions import IsAuthenticated, IsAdminUser
from rest_framework.response import Response
from rest_framework.views import APIView
from .verification import verify_application
from .models import (
    NutritionistApplication,
    NutritionistProfile,
)
from rest_framework import status as http_status
from django.shortcuts import get_object_or_404
from .renderers import CamelCaseAPIMixin, CamelCaseMultipartAPIMixin
from .serializers import (
    NutritionistApplicationSerializer,
    NutritionistProfileSerializer,
)


class NutritionistListView(CamelCaseAPIMixin, APIView):
    """
    GET /api/nutritionists/

    Public-ish browse list mobile's appointments.ts needs to let a
    client pick who to book with. Only verified nutritionists are
    shown. Optional ?specialization= filter for a simple substring
    match.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):

        nutritionists = NutritionistProfile.objects.filter(
            is_verified=True
        ).select_related("user")

        specialization = request.query_params.get("specialization")

        if specialization:
            nutritionists = nutritionists.filter(
                specialization__icontains=specialization
            )

        serializer = NutritionistProfileSerializer(
            nutritionists,
            many=True,
        )

        return Response(serializer.data)


class NutritionistApplicationCreateView(CamelCaseMultipartAPIMixin, APIView):
    """
    Multipart (file upload) view, so it uses CamelCaseMultipartAPIMixin
    instead of CamelCaseAPIMixin — that mixin's parser_classes
    (CamelCaseMultiPartParser/CamelCaseFormParser) replace the plain
    MultiPartParser/FormParser this view used to hardcode, so camelCase
    text fields in the multipart body still get converted the same way
    a JSON body would.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):

        # Prevent duplicate applications
        if NutritionistApplication.objects.filter(
            user=request.user
        ).exists():

            return Response(
                {
                    "detail": "You already have a nutritionist application."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = NutritionistApplicationSerializer(
            data=request.data
        )

        if not serializer.is_valid():

            return Response(
                serializer.errors,
                status=status.HTTP_400_BAD_REQUEST
            )

        application = serializer.save(
            user=request.user
        )
        # Run initial license verification
        verify_application(application)

        return Response(
            NutritionistApplicationSerializer(application).data,
            status=status.HTTP_201_CREATED
        )


class NutritionistApplicationAIVerifyView(CamelCaseAPIMixin, APIView):
    """POST /api/nutritionists/applications/<id>/ai-verify/
    Re-runs the AI verification engine and returns the result."""
    permission_classes = [IsAdminUser]   # or your own admin/staff permission

    def post(self, request, application_id):
        application = get_object_or_404(NutritionistApplication, pk=application_id)
        result = verify_application(application)
        return Response(
            {
                "application_id": application.id,
                "ai_status": application.ai_status,
                "ai_score": application.ai_score,
                "ai_result": result,
            },
            status=http_status.HTTP_200_OK,
        )


class MyNutritionistApplicationView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        try:
            application = NutritionistApplication.objects.get(
                user=request.user
            )

        except NutritionistApplication.DoesNotExist:

            return Response(
                {
                    "detail": "You do not have a nutritionist application."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            NutritionistApplicationSerializer(
                application
            ).data
        )


class NutritionistApplicationReviewView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAdminUser]

    def patch(self, request, application_id):

        try:
            application = NutritionistApplication.objects.get(
                id=application_id
            )

        except NutritionistApplication.DoesNotExist:

            return Response(
                {
                    "detail": "Application not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        new_status = request.data.get("status")

        if new_status not in ["approved", "rejected"]:

            return Response(
                {
                    "detail": (
                        "Status must be either "
                        "'approved' or 'rejected'."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        if new_status == "rejected":

            rejection_reason = request.data.get(
                "rejection_reason",
                ""
            )

            application.status = "rejected"

            application.rejection_reason = rejection_reason

            application.reviewed_at = timezone.now()

            application.save()

            return Response(
                {
                    "message": "Nutritionist application rejected.",
                    "application": NutritionistApplicationSerializer(
                        application
                    ).data,
                }
            )

        # APPROVAL

        application.status = "approved"

        application.reviewed_at = timezone.now()

        application.save()

        profile, created = NutritionistProfile.objects.get_or_create(
            user=application.user,
            defaults={
                "specialization": application.specialization,
                "qualification": application.degree,
                "years_of_experience": application.years_of_experience,
                "license_number": application.license_number,
                "is_verified": True,
            }
        )

        if not created:

            profile.specialization = application.specialization
            profile.qualification = application.degree
            profile.years_of_experience = (
                application.years_of_experience
            )
            profile.license_number = application.license_number
            profile.is_verified = True

            profile.save()

        return Response(
            {
                "message": (
                    "Nutritionist approved successfully."
                ),
                "application": NutritionistApplicationSerializer(
                    application
                ).data,
                "profile": NutritionistProfileSerializer(
                    profile
                ).data,
            }
        )


class NutritionistProfileView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        try:
            profile = NutritionistProfile.objects.get(
                user=request.user
            )

        except NutritionistProfile.DoesNotExist:

            return Response(
                {
                    "detail": "Nutritionist profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        return Response(
            NutritionistProfileSerializer(profile).data
        )

    def patch(self, request):

        try:
            profile = NutritionistProfile.objects.get(
                user=request.user
            )

        except NutritionistProfile.DoesNotExist:

            return Response(
                {
                    "detail": "Nutritionist profile not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        serializer = NutritionistProfileSerializer(
            profile,
            data=request.data,
            partial=True
        )

        if serializer.is_valid():

            serializer.save()

            return Response(
                serializer.data
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )
