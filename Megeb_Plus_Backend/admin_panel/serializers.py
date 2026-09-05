from rest_framework import serializers
from accounts.models import User, StaffApplication
from appointments.models import Appointment
from .models import PlatformSettings


class AdminUserSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name")
    status = serializers.SerializerMethodField()
    joinedDate = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ["id", "name", "email", "status", "joinedDate"]

    def get_status(self, obj):
        return "Active" if obj.is_active else "Suspended"

    def get_joinedDate(self, obj):
        return obj.created_at.strftime("%Y-%m-%d")


class AdminNutritionistSerializer(serializers.ModelSerializer):
    name = serializers.CharField(source="full_name")
    specialty = serializers.SerializerMethodField()
    credentialType = serializers.SerializerMethodField()
    licenseNumber = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()
    appliedDate = serializers.SerializerMethodField()

    class Meta:
        model = StaffApplication
        fields = ["id", "name", "email", "specialty", "credentialType", "licenseNumber", "status", "appliedDate"]

    def get_specialty(self, obj):
        data = obj.application_data or {}
        return data.get("specialty") or data.get("specialization") or ""

    def get_credentialType(self, obj):
        data = obj.application_data or {}
        return data.get("credentialType") or data.get("credential_type") or data.get("degree") or ""

    def get_licenseNumber(self, obj):
        data = obj.application_data or {}
        return data.get("licenseNumber") or data.get("license_number") or ""

    def get_status(self, obj):
        return obj.status.capitalize()

    def get_appliedDate(self, obj):
        return obj.created_at.strftime("%Y-%m-%d")


class AdminAppointmentSerializer(serializers.ModelSerializer):
    client = serializers.CharField(source="client.full_name")
    nutritionist = serializers.CharField(source="nutritionist.full_name")
    date = serializers.SerializerMethodField()
    time = serializers.SerializerMethodField()
    status = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = ["id", "client", "nutritionist", "date", "time", "status"]

    def get_date(self, obj):
        return obj.date.strftime("%Y-%m-%d")

    def get_time(self, obj):
        return obj.time.strftime("%I:%M %p").lstrip("0")

    def get_status(self, obj):
        # Frontend's AppointmentStatus type only has 3 states (no "completed"),
        # so completed appointments are shown as Confirmed for now.
        mapping = {
            "pending": "Pending",
            "confirmed": "Confirmed",
            "cancelled": "Cancelled",
            "completed": "Confirmed",
        }
        return mapping.get(obj.status, obj.status.capitalize())


class PlatformSettingsSerializer(serializers.ModelSerializer):
    platformName = serializers.CharField(source="platform_name")
    supportEmail = serializers.EmailField(source="support_email", required=False, allow_blank=True)
    maintenanceMode = serializers.BooleanField(source="maintenance_mode")
    emailNotifications = serializers.BooleanField(source="email_notifications")

    class Meta:
        model = PlatformSettings
        fields = ["platformName", "supportEmail", "maintenanceMode", "emailNotifications"]