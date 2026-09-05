from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.utils.timesince import timesince
from django.db.models import Count
from django.db.models.functions import TruncMonth
from datetime import timedelta

from accounts.models import User, StaffApplication
from accounts.views import _approve_application, _reject_application
from appointments.models import Appointment

from .permissions import IsAdminRole
from .models import PlatformSettings
from .serializers import (
    AdminUserSerializer,
    AdminNutritionistSerializer,
    AdminAppointmentSerializer,
    PlatformSettingsSerializer,
)


# ---------------------------
# Users
# ---------------------------

class AdminUserListView(APIView):
    """Admin-only: list all platform users (for Users page)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        users = User.objects.exclude(role="admin").order_by("-created_at")
        return Response(AdminUserSerializer(users, many=True).data)


class AdminUserDetailView(APIView):
    """Admin-only: suspend/reactivate a user."""

    permission_classes = [IsAdminRole]

    def patch(self, request, user_id):
        user = User.objects.filter(id=user_id).first()

        if not user:
            return Response({"detail": "User not found."}, status=status.HTTP_404_NOT_FOUND)

        new_status = request.data.get("status")
        if new_status not in ["Active", "Suspended"]:
            return Response({"detail": "status must be 'Active' or 'Suspended'."}, status=status.HTTP_400_BAD_REQUEST)

        user.is_active = (new_status == "Active")
        user.save()

        return Response(AdminUserSerializer(user).data)


# ---------------------------
# Nutritionists
# ---------------------------

class AdminNutritionistListView(APIView):
    """Admin-only: list all nutritionist applications, any status (for Nutritionists page)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        applications = StaffApplication.objects.filter(role="nutritionist").order_by("-created_at")
        return Response(AdminNutritionistSerializer(applications, many=True).data)


class AdminNutritionistDetailView(APIView):
    """Admin-only: approve/reject a nutritionist application from the admin panel."""

    permission_classes = [IsAdminRole]

    def patch(self, request, application_id):
        application = StaffApplication.objects.filter(id=application_id, role="nutritionist").first()

        if not application:
            return Response({"detail": "Application not found."}, status=status.HTTP_404_NOT_FOUND)

        if application.status != "pending":
            return Response({"detail": "Application already reviewed."}, status=status.HTTP_400_BAD_REQUEST)

        new_status = request.data.get("status")
        if new_status not in ["Approved", "Rejected"]:
            return Response({"detail": "status must be 'Approved' or 'Rejected'."}, status=status.HTTP_400_BAD_REQUEST)

        if new_status == "Approved":
            _approve_application(application, request.user)
        else:
            _reject_application(application, request.user)

        return Response(AdminNutritionistSerializer(application).data)


# ---------------------------
# Appointments
# ---------------------------

class AdminAppointmentListView(APIView):
    """Admin-only: list every appointment across every nutritionist (for Appointments page)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        appointments = Appointment.objects.select_related(
            "user", "slot", "slot__nutritionist"
        ).order_by("-created_at")
        return Response(AdminAppointmentSerializer(appointments, many=True).data)


# ---------------------------
# Reports
# ---------------------------

class AdminReportsView(APIView):
    """Admin-only: platform-wide metrics + monthly signup trend for the Reports page."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        now = timezone.now()
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_users = User.objects.exclude(role="admin").count()
        total_nutritionists = User.objects.filter(role="nutritionist").count()
        total_appointments = Appointment.objects.count()
        completed_appointments = Appointment.objects.filter(status="completed").count()
        new_users_this_month = User.objects.exclude(role="admin").filter(
            created_at__gte=this_month_start
        ).count()

        metrics = [
            {"label": "Total Users", "value": str(total_users), "change": f"+{new_users_this_month} this month"},
            {"label": "Nutritionists", "value": str(total_nutritionists), "change": "active professionals"},
            {"label": "Appointments", "value": str(total_appointments), "change": f"{completed_appointments} completed"},
            {"label": "New Users", "value": str(new_users_this_month), "change": "this month"},
        ]

        six_months_start = (now.replace(day=1) - timedelta(days=150)).replace(day=1)
        signups = (
            User.objects.exclude(role="admin")
            .filter(created_at__gte=six_months_start)
            .annotate(month=TruncMonth("created_at"))
            .values("month")
            .annotate(count=Count("id"))
            .order_by("month")
        )

        monthly_signups = [
            {"month": row["month"].strftime("%b"), "value": row["count"]}
            for row in signups
        ]

        return Response({"metrics": metrics, "monthlySignups": monthly_signups})


# ---------------------------
# Dashboard
# ---------------------------

class AdminDashboardStatsView(APIView):
    """
    Admin-only: the 4 headline stat cards on the Dashboard page.
    Shape: {title, value, change, description, icon} — deliberately different
    from AdminReportsView's {label, value, change}, since dashboard/page.tsx
    and reports/page.tsx expect different field names and dashboard needs an
    'icon' key the StatCard component uses to pick a lucide-react icon.
    """

    permission_classes = [IsAdminRole]

    def get(self, request):
        now = timezone.now()
        this_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

        total_users = User.objects.exclude(role="admin").count()
        total_nutritionists = User.objects.filter(role="nutritionist").count()
        appointments_this_month = Appointment.objects.filter(created_at__gte=this_month_start).count()
        new_users_this_month = User.objects.exclude(role="admin").filter(
            created_at__gte=this_month_start
        ).count()

        stats = [
            {
                "title": "Total Users",
                "value": str(total_users),
                "change": f"+{new_users_this_month}",
                "description": "registered users",
                "icon": "users",
            },
            {
                "title": "Nutritionists",
                "value": str(total_nutritionists),
                "change": "",
                "description": "active professionals",
                "icon": "doctor",
            },
            {
                "title": "Appointments",
                "value": str(appointments_this_month),
                "change": "",
                "description": "this month",
                "icon": "calendar",
            },
            {
                # Revenue has no real data source yet — payments hasn't been built.
                # Showing 0 rather than a fabricated number.
                "title": "Revenue",
                "value": "0 ETB",
                "change": "",
                "description": "this month",
                "icon": "money",
            },
        ]

        return Response(stats)


# ---------------------------
# Settings
# ---------------------------

class AdminSettingsView(APIView):
    """Admin-only: view/edit platform-wide configuration (singleton row)."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        settings_obj = PlatformSettings.load()
        return Response(PlatformSettingsSerializer(settings_obj).data)

    def put(self, request):
        settings_obj = PlatformSettings.load()
        serializer = PlatformSettingsSerializer(settings_obj, data=request.data)

        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


# ---------------------------
# Sidebar badges & dashboard verification widget
# ---------------------------

class AdminVerificationRequestsView(APIView):
    """
    Admin-only: pending nutritionist applications, reshaped for the dashboard's
    VerificationRequests widget: {id, name, specialty, submitted}.
    """

    permission_classes = [IsAdminRole]

    def get(self, request):
        status_param = request.query_params.get("status", "pending")
        applications = StaffApplication.objects.filter(
            role="nutritionist", status=status_param
        ).order_by("-created_at")

        data = [
            {
                "id": app.id,
                "name": app.full_name,
                "specialty": (app.application_data or {}).get("specialty")
                or (app.application_data or {}).get("specialization")
                or "",
                "submitted": f"{timesince(app.created_at)} ago",
            }
            for app in applications
        ]

        return Response(data)


class AdminVerificationCountView(APIView):
    """Admin-only: count of nutritionist applications by status, for the sidebar badge."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        status_param = request.query_params.get("status", "pending")
        count = StaffApplication.objects.filter(role="nutritionist", status=status_param).count()
        return Response({"count": count})


class AdminFoodVendorCountView(APIView):
    """
    Admin-only: count of vendor applications by status, for the sidebar badge.
    NOTE: assumes vendor applications go through the same StaffApplication model
    as nutritionists (confirmed true as of this writing — one vendor test
    application exists). If the vendor teammate builds a separate application
    flow/model later, this endpoint will need to point at that instead.
    """

    permission_classes = [IsAdminRole]

    def get(self, request):
        status_param = request.query_params.get("status", "pending")
        count = StaffApplication.objects.filter(role="vendor", status=status_param).count()
        return Response({"count": count})