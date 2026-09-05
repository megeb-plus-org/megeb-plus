from django.conf import settings
from django.db import models


class Appointment(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("confirmed", "Confirmed"),
        ("cancelled", "Cancelled"),
        ("completed", "Completed"),
    ]

    MODE_CHOICES = [
        ("online", "Online"),
        ("in_person", "In Person"),
    ]

    TYPE_CHOICES = [
        ("consultation", "Consultation"),
        ("follow_up", "Follow Up"),
        ("nutrition_plan", "Nutrition Plan"),
    ]

    nutritionist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nutritionist_appointments",
    )

    client = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="client_appointments",
    )

    appointment_type = models.CharField(
        max_length=50,
        choices=TYPE_CHOICES,
        default="consultation",
    )

    date = models.DateField()

    time = models.TimeField()

    mode = models.CharField(
        max_length=20,
        choices=MODE_CHOICES,
        default="online",
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending",
    )

    notes = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f"{self.client} - {self.nutritionist} - {self.date}"


class NutritionistAvailability(models.Model):

    DAYS_OF_WEEK = [
        (0, "Monday"),
        (1, "Tuesday"),
        (2, "Wednesday"),
        (3, "Thursday"),
        (4, "Friday"),
        (5, "Saturday"),
        (6, "Sunday"),
    ]

    nutritionist = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availability_slots",
    )

    day_of_week = models.PositiveSmallIntegerField(
        choices=DAYS_OF_WEEK,
    )

    start_time = models.TimeField()

    end_time = models.TimeField()

    is_active = models.BooleanField(
        default=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["day_of_week", "start_time"]

    def __str__(self):
        return (
            f"{self.nutritionist} - "
            f"{self.get_day_of_week_display()} "
            f"{self.start_time} - {self.end_time}"
        )


class Consultation(models.Model):

    STATUS_CHOICES = [
        ("waiting", "Waiting"),
        ("active", "Active"),
        ("completed", "Completed"),
        ("cancelled", "Cancelled"),
    ]

    appointment = models.OneToOneField(
        Appointment,
        on_delete=models.CASCADE,
        related_name="consultation",
    )

    meeting_id = models.CharField(
        max_length=255,
        blank=True,
        null=True
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="waiting",
    )

    room_id = models.CharField(
        max_length=255,
        unique=True,
        blank=True,
        null=True,
    )

    meeting_url = models.URLField(
        blank=True,
        null=True,
    )

    started_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    ended_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    nutritionist_notes = models.TextField(
        blank=True,
        null=True,
    )

    client_notes = models.TextField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return f"Consultation - Appointment {self.appointment.id}"