from datetime import datetime, timedelta

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from django.utils import timezone
from django.db.models import Q
from .models import Appointment, Consultation, NutritionistAvailability
from .serializers import AppointmentSerializer, ConsultationSerializer, NutritionistAvailabilitySerializer
from .renderers import CamelCaseAPIMixin
import uuid
from chat.models import Conversation

# Default length of one bookable slot when carving up a
# NutritionistAvailability window into concrete times for
# /appointments/available-slots/. Not modeled on Appointment yet
# (no duration field), so this is a fixed assumption for now.
SLOT_DURATION_MINUTES = 30


class NutritionistAppointmentListView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        appointments = Appointment.objects.filter(
            nutritionist=request.user
        ).order_by("date", "time")

        serializer = AppointmentSerializer(
            appointments,
            many=True
        )

        return Response(serializer.data)


class ClientAppointmentListView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):

        appointments = Appointment.objects.filter(
            client=request.user
        ).order_by("date", "time")

        serializer = AppointmentSerializer(
            appointments,
            many=True
        )

        return Response(serializer.data)


class UpcomingAppointmentsView(CamelCaseAPIMixin, APIView):
    """
    GET /api/appointments/upcoming/

    Mobile's appointments.ts types this as
    `getUpcomingAppointment(): Promise<Appointment | null>` — a single
    appointment, not a list. Without having to know whether the
    logged-in user is the client or the nutritionist on the booking
    (unlike the client/ and nutritionist/ list views above, which
    require knowing your role), this returns the single soonest
    pending/confirmed appointment where the user is on either side,
    today-or-later — or `null` if there isn't one.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):

        now = timezone.localtime()
        today = now.date()

        appointment = Appointment.objects.filter(
            Q(client=request.user) | Q(nutritionist=request.user),
            status__in=["pending", "confirmed"],
        ).filter(
            Q(date__gt=today) | Q(date=today, time__gte=now.time())
        ).order_by("date", "time").first()

        if appointment is None:
            return Response(None)

        return Response(AppointmentSerializer(appointment).data)


class AppointmentCreateView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request):

        serializer = AppointmentSerializer(
            data=request.data
        )

        if serializer.is_valid():

            appointment = serializer.save()
            Conversation.objects.get_or_create(
            client=appointment.client,
            nutritionist=appointment.nutritionist,
            
)
            return Response(
                AppointmentSerializer(appointment).data,
                status=status.HTTP_201_CREATED
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST
        )


class AppointmentDetailView(CamelCaseAPIMixin, APIView):
    """
    GET    /api/appointments/{id}/  -> single appointment
    DELETE /api/appointments/{id}/  -> mobile's "cancel/remove
           appointment" action.

    A hard delete would destroy history (and orphan the Consultation
    row via CASCADE), so DELETE marks the appointment cancelled
    instead of removing the row — same rule CancelAppointmentView
    already enforces, just reachable at the REST-conventional URL
    mobile calls.
    """

    permission_classes = [IsAuthenticated]

    def _get_appointment(self, appointment_id):
        try:
            return Appointment.objects.get(id=appointment_id)
        except Appointment.DoesNotExist:
            return None

    def get(self, request, appointment_id):

        appointment = self._get_appointment(appointment_id)

        if appointment is None:
            return Response(
                {"detail": "Appointment not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if (
            appointment.client != request.user
            and appointment.nutritionist != request.user
        ):
            return Response(
                {"detail": "You are not part of this appointment."},
                status=status.HTTP_403_FORBIDDEN
            )

        return Response(AppointmentSerializer(appointment).data)

    def delete(self, request, appointment_id):

        appointment = self._get_appointment(appointment_id)

        if appointment is None:
            return Response(
                {"detail": "Appointment not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        if (
            appointment.client != request.user
            and appointment.nutritionist != request.user
        ):
            return Response(
                {"detail": "You are not allowed to cancel this appointment."},
                status=status.HTTP_403_FORBIDDEN
            )

        if appointment.status == "completed":
            return Response(
                {"detail": "Completed appointments cannot be cancelled."},
                status=status.HTTP_400_BAD_REQUEST
            )

        if appointment.status == "cancelled":
            return Response(status=status.HTTP_204_NO_CONTENT)

        appointment.status = "cancelled"
        appointment.save()

        return Response(status=status.HTTP_204_NO_CONTENT)


class ConfirmAppointmentView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, appointment_id):

        try:
            appointment = Appointment.objects.get(
                id=appointment_id
            )

        except Appointment.DoesNotExist:

            return Response(
                {
                    "detail": "Appointment not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Only the assigned nutritionist can confirm
        if appointment.nutritionist != request.user:

            return Response(
                {
                    "detail": "Only the assigned nutritionist can confirm this appointment."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Appointment must still be pending
        if appointment.status != "pending":

            return Response(
                {
                    "detail": "Only pending appointments can be confirmed."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        appointment.status = "confirmed"
        appointment.save()

        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_200_OK
        )


class CancelAppointmentView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, appointment_id):

        try:
            appointment = Appointment.objects.get(
                id=appointment_id
            )

        except Appointment.DoesNotExist:

            return Response(
                {
                    "detail": "Appointment not found."
                },
                status=status.HTTP_404_NOT_FOUND
            )

        # Only the client or assigned nutritionist can cancel
        if (
            appointment.client != request.user
            and appointment.nutritionist != request.user
        ):

            return Response(
                {
                    "detail": "You are not allowed to cancel this appointment."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Cannot cancel an already completed appointment
        if appointment.status == "completed":

            return Response(
                {
                    "detail": "Completed appointments cannot be cancelled."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Cannot cancel an already cancelled appointment
        if appointment.status == "cancelled":

            return Response(
                {
                    "detail": "Appointment is already cancelled."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        appointment.status = "cancelled"
        appointment.save()

        return Response(
            AppointmentSerializer(appointment).data,
            status=status.HTTP_200_OK
        )


class CreateConsultationView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def post(self, request, appointment_id):

        try:
            appointment = Appointment.objects.get(
                id=appointment_id
            )

        except Appointment.DoesNotExist:
            return Response(
                {"detail": "Appointment not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        # Only the client or nutritionist can create the consultation
        if (
            request.user != appointment.client
            and request.user != appointment.nutritionist
        ):
            return Response(
                {
                    "detail": "You are not part of this appointment."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        # Appointment must be confirmed
        if appointment.status != "confirmed":
            return Response(
                {
                    "detail": (
                        "A consultation can only be created "
                        "for a confirmed appointment."
                    )
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Don't create duplicate consultations
        if Consultation.objects.filter(
            appointment=appointment
        ).exists():
            return Response(
                {
                    "detail": "A consultation already exists."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate unique Jitsi room
        room_id = f"megebplus-{uuid.uuid4().hex}"

        meeting_url = (
            f"https://meet.jit.si/{room_id}"
        )

        consultation = Consultation.objects.create(
            appointment=appointment,
            room_id=room_id,
            meeting_id=room_id,
            meeting_url=meeting_url,
        )

        return Response(
            ConsultationSerializer(
                consultation
            ).data,
            status=status.HTTP_201_CREATED
        )


class StartConsultationView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, consultation_id):

        try:
            consultation = Consultation.objects.select_related(
                "appointment"
            ).get(id=consultation_id)

        except Consultation.DoesNotExist:
            return Response(
                {"detail": "Consultation not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        appointment = consultation.appointment

        # Only the client or nutritionist can start
        if (
            request.user != appointment.client
            and request.user != appointment.nutritionist
        ):
            return Response(
                {
                    "detail": "You are not part of this consultation."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if consultation.status != "waiting":
            return Response(
                {
                    "detail": "Consultation cannot be started."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        # Generate a unique room
        room_id = (
            f"megeb-consultation-{consultation.id}-"
            f"{uuid.uuid4().hex[:10]}"
        )

        meeting_url = f"https://meet.jit.si/{room_id}"

        consultation.status = "active"
        consultation.room_id = room_id
        consultation.meeting_url = meeting_url
        consultation.started_at = timezone.now()

        consultation.save(
            update_fields=[
                "status",
                "room_id",
                "meeting_url",
                "started_at",
                "updated_at",
            ]
        )

        return Response(
            ConsultationSerializer(consultation).data,
            status=status.HTTP_200_OK
        )


class EndConsultationView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, consultation_id):

        try:
            consultation = Consultation.objects.select_related(
                "appointment"
            ).get(id=consultation_id)

        except Consultation.DoesNotExist:
            return Response(
                {"detail": "Consultation not found."},
                status=status.HTTP_404_NOT_FOUND
            )

        appointment = consultation.appointment

        if (
            request.user != appointment.client
            and request.user != appointment.nutritionist
        ):
            return Response(
                {
                    "detail": "You are not part of this consultation."
                },
                status=status.HTTP_403_FORBIDDEN
            )

        if consultation.status != "active":
            return Response(
                {
                    "detail": "Only active consultations can be ended."
                },
                status=status.HTTP_400_BAD_REQUEST
            )

        consultation.status = "completed"
        consultation.ended_at = timezone.now()

        consultation.save(
            update_fields=[
                "status",
                "ended_at",
                "updated_at",
            ]
        )

        appointment.status = "completed"
        appointment.save(
            update_fields=[
                "status",
                "updated_at",
            ]
        )

        return Response(
            ConsultationSerializer(consultation).data,
            status=status.HTTP_200_OK
        )


class NutritionistAvailabilityView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def get(self, request):
        availability = NutritionistAvailability.objects.filter(
            nutritionist=request.user,
            is_active=True,
        )

        serializer = NutritionistAvailabilitySerializer(
            availability,
            many=True,
        )

        return Response(serializer.data)

    def post(self, request):

        serializer = NutritionistAvailabilitySerializer(
            data=request.data
        )

        if serializer.is_valid():

            availability = serializer.save(
                nutritionist=request.user
            )

            return Response(
                NutritionistAvailabilitySerializer(
                    availability
                ).data,
                status=status.HTTP_201_CREATED,
            )

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )


class NutritionistAvailabilityDetailView(CamelCaseAPIMixin, APIView):

    permission_classes = [IsAuthenticated]

    def patch(self, request, availability_id):

        try:
            availability = NutritionistAvailability.objects.get(
                id=availability_id,
                nutritionist=request.user,
            )

        except NutritionistAvailability.DoesNotExist:

            return Response(
                {
                    "detail": "Availability slot not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        serializer = NutritionistAvailabilitySerializer(
            availability,
            data=request.data,
            partial=True,
        )

        if serializer.is_valid():

            serializer.save()

            return Response(serializer.data)

        return Response(
            serializer.errors,
            status=status.HTTP_400_BAD_REQUEST,
        )

    def delete(self, request, availability_id):

        try:
            availability = NutritionistAvailability.objects.get(
                id=availability_id,
                nutritionist=request.user,
            )

        except NutritionistAvailability.DoesNotExist:

            return Response(
                {
                    "detail": "Availability slot not found."
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        availability.delete()

        return Response(
            status=status.HTTP_204_NO_CONTENT
        )


class AvailableSlotsView(CamelCaseAPIMixin, APIView):
    """
    GET /api/appointments/available-slots/?nutritionist=<id>&date=YYYY-MM-DD

    Mobile's appointments.ts types this as
    `getAvailableTimeSlots(): Promise<string[]>` — a flat array of
    time strings, not a wrapper object. This carves a nutritionist's
    recurring weekly NutritionistAvailability window for that date's
    weekday into fixed-length slots, and drops any slot that's
    already booked (pending/confirmed) on that date.

    Query params:
      nutritionist  - required, nutritionist user id
      date          - required, YYYY-MM-DD
      duration      - optional, minutes per slot (default 30)
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):

        nutritionist_id = request.query_params.get("nutritionist")
        date_str = request.query_params.get("date")

        if not nutritionist_id or not date_str:
            return Response(
                {
                    "detail": "Both 'nutritionist' and 'date' query params are required."
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            target_date = datetime.strptime(date_str, "%Y-%m-%d").date()
        except ValueError:
            return Response(
                {"detail": "'date' must be in YYYY-MM-DD format."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        try:
            duration = int(request.query_params.get("duration", SLOT_DURATION_MINUTES))
        except ValueError:
            duration = SLOT_DURATION_MINUTES

        # NutritionistAvailability.day_of_week: 0=Monday ... 6=Sunday,
        # which matches date.weekday() directly.
        day_of_week = target_date.weekday()

        windows = NutritionistAvailability.objects.filter(
            nutritionist_id=nutritionist_id,
            day_of_week=day_of_week,
            is_active=True,
        )

        booked_times = set(
            Appointment.objects.filter(
                nutritionist_id=nutritionist_id,
                date=target_date,
                status__in=["pending", "confirmed"],
            ).values_list("time", flat=True)
        )

        slots = []
        step = timedelta(minutes=duration)

        for window in windows:
            current = datetime.combine(target_date, window.start_time)
            end = datetime.combine(target_date, window.end_time)

            while current + step <= end:
                slot_time = current.time()

                if slot_time not in booked_times:
                    slots.append(slot_time.strftime("%H:%M"))

                current += step

        return Response(slots)
