from django.conf import settings
from django.db import models
from django.utils import timezone


class PaymentTransaction(models.Model):
    STATUS_PENDING = "pending"
    STATUS_SUCCESSFUL = "successful"
    STATUS_FAILED = "failed"
    STATUS_CANCELLED = "cancelled"
    STATUS_EXPIRED = "expired"

    STATUS_CHOICES = [
        (STATUS_PENDING, "Pending"),
        (STATUS_SUCCESSFUL, "Successful"),
        (STATUS_FAILED, "Failed"),
        (STATUS_CANCELLED, "Cancelled"),
        (STATUS_EXPIRED, "Expired"),
    ]

    PROVIDER_STARPAY = "starpay"

    PAYMENT_METHOD_USSD = "ussd"
    PAYMENT_METHOD_CARD = "card"
    PAYMENT_METHOD_BANK = "bank"

    PAYMENT_METHOD_CHOICES = [
        (PAYMENT_METHOD_USSD, "USSD"),
        (PAYMENT_METHOD_CARD, "Card"),
        (PAYMENT_METHOD_BANK, "Bank"),
    ]

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="payment_transactions",
    )

    # One appointment can have one payment.
    appointment = models.OneToOneField(
        "appointments.Appointment",
        on_delete=models.PROTECT,
        related_name="payment",
        null=True,
        blank=True,
    )

    reference = models.CharField(
        max_length=100,
        unique=True,
    )

    starpay_order_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        db_index=True,
    )

    starpay_transaction_id = models.CharField(
        max_length=100,
        blank=True,
        null=True,
    )

    amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
    )

    currency = models.CharField(
        max_length=10,
        default="ETB",
    )

    # These values are saved when the payment is created.
    # They should never change when the nutritionist later changes their fee.
    platform_fee = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    nutritionist_amount = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        default=0,
    )

    commission_percentage = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0,
    )

    payment_method = models.CharField(
        max_length=20,
        choices=PAYMENT_METHOD_CHOICES,
        default=PAYMENT_METHOD_USSD,
    )

    provider = models.CharField(
        max_length=30,
        default=PROVIDER_STARPAY,
    )

    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )

    description = models.CharField(
        max_length=255,
        blank=True,
    )

    provider_response = models.JSONField(
        blank=True,
        null=True,
    )

    callback_received_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    paid_at = models.DateTimeField(
        blank=True,
        null=True,
    )

    expires_at = models.DateTimeField(
        blank=True,
        null=True,
        db_index=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    class Meta:
        ordering = ["-created_at"]

    def __str__(self):
        return (
            f"{self.reference} - "
            f"{self.amount} {self.currency} - "
            f"{self.status}"
        )

    def is_expired(self):
        if not self.expires_at:
            return False

        return timezone.now() >= self.expires_at

    def expire_if_needed(self):
        if (
            self.status == self.STATUS_PENDING
            and self.is_expired()
        ):
            self.status = self.STATUS_EXPIRED

            self.save(
                update_fields=[
                    "status",
                    "updated_at",
                ]
            )

            return True

        return False