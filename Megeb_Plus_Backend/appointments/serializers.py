from rest_framework import serializers
from .models import NutritionistAvailability
from .models import Appointment, Consultation
from nutritionists.models import NutritionistProfile


class AppointmentSerializer(serializers.ModelSerializer):

    nutritionist_name = serializers.CharField(
        source="nutritionist.full_name",
        read_only=True
    )

    client_name = serializers.CharField(
        source="client.full_name",
        read_only=True
    )

    class Meta:
        model = Appointment

        fields = [
            "id",
            "nutritionist",
            "nutritionist_name",
            "client",
            "client_name",
            "appointment_type",
            "date",
            "time",
            "mode",
            "status",
            "notes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "nutritionist_name",
            "client_name",
            "created_at",
            "updated_at",
        ]

    def validate(self, attrs):

        nutritionist = attrs.get("nutritionist")

        # Make sure the selected user is actually
        # an approved/verified nutritionist.
        try:
            profile = nutritionist.nutritionist_profile
        except NutritionistProfile.DoesNotExist:
            raise serializers.ValidationError({
                "nutritionist": "This user is not a nutritionist."
            })

        if not profile.is_verified:
            raise serializers.ValidationError({
                "nutritionist": "This nutritionist is not verified."
            })

        return attrs
class ConsultationSerializer(serializers.ModelSerializer):

    appointment_id = serializers.IntegerField(
        source="appointment.id",
        read_only=True
    )

    class Meta:
        model = Consultation

        fields = [
            "id",
            "appointment_id",
            "status",
            "room_id",
            "meeting_url",
            "started_at",
            "ended_at",
            "nutritionist_notes",
            "client_notes",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "appointment_id",
            "status",
            "room_id",
            "meeting_url",
            "started_at",
            "ended_at",
            "created_at",
            "updated_at",
        ]

class NutritionistAvailabilitySerializer(serializers.ModelSerializer):

    day_name = serializers.CharField(
        source="get_day_of_week_display",
        read_only=True,
    )

    class Meta:
        model = NutritionistAvailability

        fields = [
            "id",
            "nutritionist",
            "day_of_week",
            "day_name",
            "start_time",
            "end_time",
            "is_active",
            "created_at",
            "updated_at",
        ]

        read_only_fields = [
            "id",
            "nutritionist",
            "day_name",
            "created_at",
            "updated_at",
        ]

    def validate(self, data):
        start_time = data.get("start_time")
        end_time = data.get("end_time")

        if start_time >= end_time:
            raise serializers.ValidationError(
                "End time must be after start time."
            )

        return data