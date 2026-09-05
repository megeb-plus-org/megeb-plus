
from rest_framework import serializers

from .models import PaymentTransaction


class CreatePaymentSerializer(serializers.Serializer):
    # The appointment that the client wants to pay for.
    appointmentId = serializers.IntegerField(
        min_value=1,
    )

    # We keep amount temporarily for compatibility with your
    # current frontend/API requests.
    #
    # IMPORTANT:
    # The backend will NOT trust this amount.
    # payments/views.py will get the real amount from the
    # nutritionist's consultation_fee.
    amount = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        min_value=1,
        required=False,
    )

    description = serializers.CharField(
        max_length=255,
        required=False,
        allow_blank=True,
    )

    customerPhoneNumber = serializers.CharField(
        max_length=30,
    )

    customerEmail = serializers.EmailField(
        required=False,
        allow_blank=True,
    )


class PaymentTransactionSerializer(serializers.ModelSerializer):
    class Meta:
        model = PaymentTransaction

        fields = [
            "reference",
            "appointment",
            "starpay_order_id",
            "starpay_transaction_id",
            "amount",
            "platform_fee",
            "nutritionist_amount",
            "currency",
            "payment_method",
            "provider",
            "status",
            "description",
            "created_at",
            "updated_at",
            "paid_at",
            "expires_at",
        ]

        read_only_fields = fields

