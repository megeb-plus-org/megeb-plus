from decimal import Decimal, ROUND_HALF_UP
import hashlib
import hmac
import uuid

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from rest_framework import status
from rest_framework.permissions import IsAuthenticated, AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from appointments.models import Appointment
from nutritionists.models import NutritionistProfile

from .models import PaymentTransaction
from .serializers import (
    CreatePaymentSerializer,
    PaymentTransactionSerializer,
)
from .starpay import (
    StarPayError,
    create_starpay_transaction,
    verify_starpay_transaction,
)


class CreatePaymentView(APIView):
    """
    Create a StarPay payment for an appointment.

    The backend determines the payment amount from the
    nutritionist's consultation fee.

    The amount sent by the client is NOT trusted.

    Payment retry behavior:
        - successful -> reject duplicate payment
        - pending -> reject duplicate payment
        - failed -> reuse existing payment
        - expired -> reuse existing payment
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = CreatePaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        appointment_id = serializer.validated_data["appointmentId"]

        customer_phone = serializer.validated_data[
            "customerPhoneNumber"
        ]

        customer_email = serializer.validated_data.get(
            "customerEmail",
            "",
        )

        # ---------------------------------------------------------
        # 1. Find the appointment
        # ---------------------------------------------------------

        try:
            appointment = (
                Appointment.objects
                .select_related(
                    "nutritionist",
                    "client",
                )
                .get(
                    id=appointment_id,
                    client=request.user,
                )
            )

        except Appointment.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": (
                        "Appointment not found or you are not "
                        "the client for this appointment."
                    ),
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ---------------------------------------------------------
        # 2. Check appointment status
        # ---------------------------------------------------------

        if appointment.status == "cancelled":
            return Response(
                {
                    "success": False,
                    "message": (
                        "You cannot pay for a cancelled appointment."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        if appointment.status == "completed":
            return Response(
                {
                    "success": False,
                    "message": (
                        "This appointment has already been completed."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 3. Get nutritionist profile
        # ---------------------------------------------------------

        try:
            nutritionist_profile = (
                appointment.nutritionist.nutritionist_profile
            )

        except NutritionistProfile.DoesNotExist:
            return Response(
                {
                    "success": False,
                    "message": (
                        "The assigned nutritionist does not have "
                        "a nutritionist profile."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 4. Nutritionist must be verified
        # ---------------------------------------------------------

        if not nutritionist_profile.is_verified:
            return Response(
                {
                    "success": False,
                    "message": "This nutritionist is not verified.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 5. Get REAL price from backend
        # ---------------------------------------------------------

        consultation_fee = nutritionist_profile.consultation_fee

        if consultation_fee is None:
            return Response(
                {
                    "success": False,
                    "message": (
                        "This nutritionist has not set a "
                        "consultation fee."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        consultation_fee = Decimal(
            str(consultation_fee)
        )

        if consultation_fee <= Decimal("0"):
            return Response(
                {
                    "success": False,
                    "message": "The consultation fee is invalid.",
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # 6. Calculate platform commission
        # ---------------------------------------------------------

        commission_percentage = Decimal(
            str(
                getattr(
                    settings,
                    "PLATFORM_COMMISSION_PERCENTAGE",
                    "0",
                )
            )
        )

        if commission_percentage < Decimal("0"):
            commission_percentage = Decimal("0")

        if commission_percentage > Decimal("100"):
            commission_percentage = Decimal("100")

        platform_fee = (
            consultation_fee
            * commission_percentage
            / Decimal("100")
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        nutritionist_amount = (
            consultation_fee - platform_fee
        ).quantize(
            Decimal("0.01"),
            rounding=ROUND_HALF_UP,
        )

        # ---------------------------------------------------------
        # 7. Find/reuse existing payment
        # ---------------------------------------------------------
        #
        # appointment has a OneToOneField in PaymentTransaction.
        #
        # Therefore:
        #
        # successful -> cannot pay again
        # pending    -> cannot create another payment
        # failed     -> reuse existing row
        # expired    -> reuse existing row
        #
        # This prevents:
        #
        # IntegrityError:
        # duplicate key value violates unique constraint
        # ---------------------------------------------------------

        with transaction.atomic():

            existing_payment = (
                PaymentTransaction.objects
                .select_for_update()
                .filter(
                    appointment=appointment,
                )
                .first()
            )

            if existing_payment:
                # Automatically mark pending payment as expired
                # when its expiration time has passed.
                existing_payment.expire_if_needed()

                # -------------------------------------------------
                # Already successfully paid
                # -------------------------------------------------

                if (
                    existing_payment.status
                    == PaymentTransaction.STATUS_SUCCESSFUL
                ):
                    return Response(
                        {
                            "success": False,
                            "message": (
                                "This appointment has already "
                                "been paid for."
                            ),
                            "reference": (
                                existing_payment.reference
                            ),
                            "status": (
                                existing_payment.status
                            ),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

                # -------------------------------------------------
                # Payment still pending
                # -------------------------------------------------

                if (
                    existing_payment.status
                    == PaymentTransaction.STATUS_PENDING
                ):
                    return Response(
                        {
                            "success": False,
                            "message": (
                                "There is already a pending payment "
                                "for this appointment."
                            ),
                            "reference": (
                                existing_payment.reference
                            ),
                            "starpayOrderId": (
                                existing_payment.starpay_order_id
                            ),
                            "status": (
                                existing_payment.status
                            ),
                        },
                        status=status.HTTP_400_BAD_REQUEST,
                    )

            # -----------------------------------------------------
            # 8. Create OR reuse local payment
            # -----------------------------------------------------

            if existing_payment:

                # -------------------------------------------------
                # Reuse failed/expired payment
                # -------------------------------------------------

                payment = existing_payment

                # Generate a NEW local reference for the retry.
                payment.reference = (
                    self.generate_reference()
                )

                payment.user = request.user
                payment.appointment = appointment

                payment.amount = consultation_fee

                payment.platform_fee = platform_fee

                payment.nutritionist_amount = (
                    nutritionist_amount
                )

                payment.currency = "ETB"

                payment.payment_method = (
                    PaymentTransaction.PAYMENT_METHOD_USSD
                )

                payment.provider = (
                    PaymentTransaction.PROVIDER_STARPAY
                )

                payment.status = (
                    PaymentTransaction.STATUS_PENDING
                )

                payment.description = (
                    f"Payment for appointment #{appointment.id}"
                )

                # Clear old StarPay attempt.
                payment.starpay_order_id = None

                payment.starpay_transaction_id = None

                payment.provider_response = None

                payment.callback_received_at = None

                payment.paid_at = None

                payment.expires_at = None

                payment.save()

            else:

                # -------------------------------------------------
                # First payment for this appointment
                # -------------------------------------------------

                payment = PaymentTransaction.objects.create(
                    user=request.user,
                    appointment=appointment,
                    reference=self.generate_reference(),
                    amount=consultation_fee,
                    platform_fee=platform_fee,
                    nutritionist_amount=nutritionist_amount,
                    currency="ETB",
                    payment_method=(
                        PaymentTransaction.PAYMENT_METHOD_USSD
                    ),
                    provider=(
                        PaymentTransaction.PROVIDER_STARPAY
                    ),
                    status=(
                        PaymentTransaction.STATUS_PENDING
                    ),
                    description=(
                        f"Payment for appointment #{appointment.id}"
                    ),
                )

        # ---------------------------------------------------------
        # 9. Create StarPay transaction
        # ---------------------------------------------------------

        try:

            customer_name = getattr(
                request.user,
                "full_name",
                str(request.user),
            )

            starpay_response = create_starpay_transaction(
                amount=consultation_fee,
                description=payment.description,
                customer_name=customer_name,
                customer_phone=customer_phone,
                customer_email=customer_email,
                reference=payment.reference,
            )

        except StarPayError as exc:

            payment.status = (
                PaymentTransaction.STATUS_FAILED
            )

            payment.provider_response = {
                "error": str(exc),
            }

            payment.save(
                update_fields=[
                    "status",
                    "provider_response",
                    "updated_at",
                ]
            )

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                    "reference": payment.reference,
                    "status": payment.status,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ---------------------------------------------------------
        # 10. Read StarPay response
        # ---------------------------------------------------------

        data = starpay_response.get(
            "data",
            {},
        )

        starpay_order_id = (
            data.get("order_id")
            or data.get("orderId")
            or starpay_response.get("order_id")
            or starpay_response.get("orderId")
        )

        payment_url = (
            data.get("payment_url")
            or data.get("paymentUrl")
            or starpay_response.get("payment_url")
            or starpay_response.get("paymentUrl")
        )

        # ---------------------------------------------------------
        # 11. StarPay must return an order ID
        # ---------------------------------------------------------

        if not starpay_order_id:

            payment.status = (
                PaymentTransaction.STATUS_FAILED
            )

            payment.provider_response = (
                starpay_response
            )

            payment.save(
                update_fields=[
                    "status",
                    "provider_response",
                    "updated_at",
                ]
            )

            return Response(
                {
                    "success": False,
                    "message": (
                        "StarPay did not return an order ID."
                    ),
                    "providerResponse": (
                        starpay_response
                    ),
                    "reference": payment.reference,
                    "status": payment.status,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ---------------------------------------------------------
        # 12. Save StarPay information
        # ---------------------------------------------------------

        payment.starpay_order_id = (
            starpay_order_id
        )

        payment.provider_response = (
            starpay_response
        )

        expires_at = self.extract_expiration(
            starpay_response
        )

        if expires_at:
            payment.expires_at = expires_at

        payment.save(
            update_fields=[
                "starpay_order_id",
                "provider_response",
                "expires_at",
                "updated_at",
            ]
        )

        # ---------------------------------------------------------
        # 13. Return payment information
        # ---------------------------------------------------------

        return Response(
            {
                "success": True,
                "message": (
                    "Payment created successfully."
                ),
                "reference": payment.reference,
                "appointmentId": appointment.id,
                "starpayOrderId": (
                    payment.starpay_order_id
                ),
                "amount": float(
                    payment.amount
                ),
                "platformFee": float(
                    payment.platform_fee
                ),
                "nutritionistAmount": float(
                    payment.nutritionist_amount
                ),
                "currency": payment.currency,
                "status": payment.status,
                "paymentUrl": payment_url,
                "expiresAt": payment.expires_at,
            },
            status=status.HTTP_201_CREATED,
        )

    @staticmethod
    def generate_reference():
        return (
            f"MEGEB-{uuid.uuid4().hex[:12].upper()}"
        )

    @staticmethod
    def extract_expiration(starpay_response):
        """
        Try to read StarPay's expiration timestamp.
        """

        data = starpay_response.get(
            "data",
            {},
        )

        expiration = (
            data.get("expired_at")
            or data.get("expires_at")
            or data.get("expiration")
            or starpay_response.get("expired_at")
            or starpay_response.get("expires_at")
        )

        if not expiration:
            return None

        if isinstance(expiration, str):

            try:

                value = expiration.replace(
                    "Z",
                    "+00:00",
                )

                return timezone.datetime.fromisoformat(
                    value
                )

            except ValueError:
                return None

        return None


class VerifyPaymentView(APIView):
    """
    Verify a payment with StarPay.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):

        starpay_order_id = request.data.get(
            "starpayOrderId"
        )

        if not starpay_order_id:
            return Response(
                {
                    "success": False,
                    "message": (
                        "starpayOrderId is required."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # Find payment
        # ---------------------------------------------------------

        try:

            payment = (
                PaymentTransaction.objects
                .select_related(
                    "appointment",
                )
                .get(
                    starpay_order_id=starpay_order_id,
                    user=request.user,
                )
            )

        except PaymentTransaction.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "message": "Payment not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ---------------------------------------------------------
        # Check local expiration
        # ---------------------------------------------------------

        payment.expire_if_needed()

        if (
            payment.status
            == PaymentTransaction.STATUS_EXPIRED
        ):
            return Response(
                {
                    "success": False,
                    "message": (
                        "This payment has expired."
                    ),
                    "reference": payment.reference,
                    "status": payment.status,
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # Verify with StarPay
        # ---------------------------------------------------------

        try:

            verification_response = (
                verify_starpay_transaction(
                    starpay_order_id
                )
            )

        except StarPayError as exc:

            return Response(
                {
                    "success": False,
                    "message": str(exc),
                    "reference": payment.reference,
                },
                status=status.HTTP_502_BAD_GATEWAY,
            )

        # ---------------------------------------------------------
        # Read StarPay status
        # ---------------------------------------------------------

        provider_data = (
            verification_response.get(
                "data",
                {},
            )
        )

        provider_status = str(
            provider_data.get(
                "status",
                verification_response.get(
                    "status",
                    "",
                ),
            )
        ).upper()

        payment.provider_response = (
            verification_response
        )

        # ---------------------------------------------------------
        # Update local payment status
        # ---------------------------------------------------------

        if provider_status == "PAID":

            payment.status = (
                PaymentTransaction.STATUS_SUCCESSFUL
            )

            # Only set paid_at if it has not already
            # been set.
            if not payment.paid_at:
                payment.paid_at = timezone.now()

        elif provider_status in [
            "FAILED",
            "FAILURE",
        ]:

            payment.status = (
                PaymentTransaction.STATUS_FAILED
            )

        elif provider_status in [
            "CANCELLED",
            "CANCELED",
        ]:

            payment.status = (
                PaymentTransaction.STATUS_CANCELLED
            )
        elif provider_status == "UNPAID":
            # StarPay verification can temporarily report UNPAID even
            # after StarPay has already sent a valid PAID callback.
            # Never downgrade a locally confirmed payment.
            #
            # A successful callback sets paid_at. Therefore preserve
            # the successful state when paid_at proves the payment was
            # already confirmed, even if verification is temporarily UNPAID.
            if (
                payment.status != PaymentTransaction.STATUS_SUCCESSFUL
                and not payment.paid_at
            ):
                payment.status = (
                    PaymentTransaction.STATUS_PENDING
                )


        # ---------------------------------------------------------
        # Update expiration
        # ---------------------------------------------------------

        expires_at = (
            CreatePaymentView.extract_expiration(
                verification_response
            )
        )

        if expires_at:
            payment.expires_at = expires_at

        payment.save(
            update_fields=[
                "status",
                "provider_response",
                "paid_at",
                "expires_at",
                "updated_at",
            ]
        )

        # ---------------------------------------------------------
        # Return result
        # ---------------------------------------------------------

        return Response(
            {
                "success": True,
                "reference": payment.reference,
                "appointmentId": (
                    payment.appointment_id
                    if payment.appointment_id
                    else None
                ),
                "starpayOrderId": (
                    payment.starpay_order_id
                ),
                "status": payment.status,
                "amount": float(
                    payment.amount
                ),
                "platformFee": float(
                    payment.platform_fee
                ),
                "nutritionistAmount": float(
                    payment.nutritionist_amount
                ),
                "currency": payment.currency,
                "providerResponse": (
                    verification_response
                ),
            }
        )


class StarPayCallbackView(APIView):
    """
    Receive payment callbacks from StarPay.

    This endpoint is public because StarPay calls it.
    The callback signature is verified before processing.
    """

    permission_classes = [AllowAny]

    def post(self, request):

        timestamp = request.headers.get(
            "X-Timestamp"
        )

        signature = request.headers.get(
            "X-Signature"
        )

        # ---------------------------------------------------------
        # Check signature headers
        # ---------------------------------------------------------

        if not timestamp or not signature:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Missing callback signature headers."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        secret = settings.STARPAY_API_SECRET

        if not secret:

            return Response(
                {
                    "success": False,
                    "message": (
                        "StarPay secret is not configured."
                    ),
                },
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        # ---------------------------------------------------------
        # Verify callback signature
        # ---------------------------------------------------------

        body = request.body.decode(
            "utf-8"
        )

        message = (
            f"{timestamp}.{body}"
        )

        expected_signature = hmac.new(
            secret.encode("utf-8"),
            message.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()

        if not hmac.compare_digest(
            expected_signature,
            signature,
        ):

            return Response(
                {
                    "success": False,
                    "message": (
                        "Invalid callback signature."
                    ),
                },
                status=status.HTTP_401_UNAUTHORIZED,
            )

        payload = request.data

        # ---------------------------------------------------------
        # Find StarPay order/reference
        # ---------------------------------------------------------

        bill_reference = (
            payload.get("billRefNo")
            or payload.get("bill_ref_no")
            or payload.get("order_id")
            or payload.get("orderId")
        )

        provider_status = str(
            payload.get(
                "status",
                "",
            )
        ).upper()

        if not bill_reference:

            return Response(
                {
                    "success": False,
                    "message": (
                        "Payment reference is missing."
                    ),
                },
                status=status.HTTP_400_BAD_REQUEST,
            )

        # ---------------------------------------------------------
        # Find local payment
        # ---------------------------------------------------------

        payment = (
            PaymentTransaction.objects
            .filter(
                starpay_order_id=bill_reference,
            )
            .first()
        )

        if not payment:

            payment = (
                PaymentTransaction.objects
                .filter(
                    reference=bill_reference,
                )
                .first()
            )

        if not payment:

            return Response(
                {
                    "success": False,
                    "message": "Payment not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        # ---------------------------------------------------------
        # Save callback
        # ---------------------------------------------------------

        payment.provider_response = payload

        payment.callback_received_at = (
            timezone.now()
        )

        # ---------------------------------------------------------
        # Update payment status
        # ---------------------------------------------------------

        if provider_status == "PAID":

            payment.status = (
                PaymentTransaction.STATUS_SUCCESSFUL
            )

            if not payment.paid_at:
                payment.paid_at = timezone.now()

        elif provider_status in [
            "FAILED",
            "FAILURE",
        ]:

            payment.status = (
                PaymentTransaction.STATUS_FAILED
            )

        elif provider_status in [
            "CANCELLED",
            "CANCELED",
        ]:

            payment.status = (
                PaymentTransaction.STATUS_CANCELLED
            )

        payment.save(
            update_fields=[
                "status",
                "provider_response",
                "callback_received_at",
                "paid_at",
                "updated_at",
            ]
        )

        return Response(
            {
                "success": True,
                "message": (
                    "Callback processed successfully."
                ),
            },
            status=status.HTTP_200_OK,
        )


class PaymentHistoryView(APIView):
    """
    Return payments made by the logged-in user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):

        payments = (
            PaymentTransaction.objects
            .filter(
                user=request.user,
            )
            .select_related(
                "appointment",
            )
        )

        # Automatically expire old pending payments.
        for payment in payments:
            payment.expire_if_needed()

        serializer = PaymentTransactionSerializer(
            payments,
            many=True,
        )

        return Response(
            {
                "success": True,
                "payments": serializer.data,
            }
        )


class PaymentDetailView(APIView):
    """
    Return one payment belonging to the logged-in user.
    """

    permission_classes = [IsAuthenticated]

    def get(
        self,
        request,
        reference,
    ):

        try:

            payment = (
                PaymentTransaction.objects
                .select_related(
                    "appointment",
                )
                .get(
                    reference=reference,
                    user=request.user,
                )
            )

        except PaymentTransaction.DoesNotExist:

            return Response(
                {
                    "success": False,
                    "message": "Payment not found.",
                },
                status=status.HTTP_404_NOT_FOUND,
            )

        payment.expire_if_needed()

        serializer = PaymentTransactionSerializer(
            payment
        )

        return Response(
            {
                "success": True,
                "payment": serializer.data,
            }
        )


class NutritionistEarningsView(APIView):
    """
    Show earnings for the logged-in nutritionist.

    Only successful payments are included.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):

        # ---------------------------------------------------------
        # 1. Check role
        # ---------------------------------------------------------

        if request.user.role != "nutritionist":

            return Response(
                {
                    "success": False,
                    "message": (
                        "Only nutritionists can access earnings."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ---------------------------------------------------------
        # 2. Get successful payments
        # ---------------------------------------------------------

        payments = (
            PaymentTransaction.objects
            .filter(
                appointment__nutritionist=request.user,
                status=(
                    PaymentTransaction.STATUS_SUCCESSFUL
                ),
            )
            .select_related(
                "appointment",
                "appointment__client",
            )
            .order_by("-paid_at")
        )

        # ---------------------------------------------------------
        # 3. Calculate totals
        # ---------------------------------------------------------

        total_gross = sum(
            (
                payment.amount
                for payment in payments
            ),
            Decimal("0"),
        )

        total_platform_fee = sum(
            (
                payment.platform_fee
                for payment in payments
            ),
            Decimal("0"),
        )

        total_earnings = sum(
            (
                payment.nutritionist_amount
                for payment in payments
            ),
            Decimal("0"),
        )

        # ---------------------------------------------------------
        # 4. Payment details
        # ---------------------------------------------------------

        payment_data = []

        for payment in payments:

            appointment = payment.appointment

            payment_data.append(
                {
                    "reference": (
                        payment.reference
                    ),
                    "appointmentId": (
                        appointment.id
                        if appointment
                        else None
                    ),
                    "clientId": (
                        appointment.client_id
                        if appointment
                        else payment.user_id
                    ),
                    "clientName": (
                        appointment.client.full_name
                        if appointment
                        else None
                    ),
                    "grossAmount": float(
                        payment.amount
                    ),
                    "platformFee": float(
                        payment.platform_fee
                    ),
                    "nutritionistAmount": float(
                        payment.nutritionist_amount
                    ),
                    "currency": (
                        payment.currency
                    ),
                    "status": (
                        payment.status
                    ),
                    "paidAt": payment.paid_at,
                }
            )

        return Response(
            {
                "success": True,
                "summary": {
                    "totalGross": float(
                        total_gross
                    ),
                    "totalPlatformFee": float(
                        total_platform_fee
                    ),
                    "totalEarnings": float(
                        total_earnings
                    ),
                    "currency": "ETB",
                },
                "payments": payment_data,
            }
        )


class AdminPaymentMonitoringView(APIView):
    """
    Admin payment monitoring.

    Shows all payments and platform totals.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):

        # ---------------------------------------------------------
        # 1. Check role
        # ---------------------------------------------------------

        if request.user.role != "admin":

            return Response(
                {
                    "success": False,
                    "message": (
                        "Only admins can access "
                        "payment monitoring."
                    ),
                },
                status=status.HTTP_403_FORBIDDEN,
            )

        # ---------------------------------------------------------
        # 2. Get all payments
        # ---------------------------------------------------------

        payments = (
            PaymentTransaction.objects
            .all()
            .select_related(
                "appointment",
                "user",
                "appointment__nutritionist",
                "appointment__client",
            )
            .order_by("-created_at")
        )

        # ---------------------------------------------------------
        # 3. Successful payments
        # ---------------------------------------------------------

        successful_payments = payments.filter(
            status=(
                PaymentTransaction.STATUS_SUCCESSFUL
            ),
        )

        # ---------------------------------------------------------
        # 4. Calculate totals
        # ---------------------------------------------------------

        total_gross = sum(
            (
                payment.amount
                for payment in successful_payments
            ),
            Decimal("0"),
        )

        total_platform_fee = sum(
            (
                payment.platform_fee
                for payment in successful_payments
            ),
            Decimal("0"),
        )

        total_nutritionist_earnings = sum(
            (
                payment.nutritionist_amount
                for payment in successful_payments
            ),
            Decimal("0"),
        )

        # ---------------------------------------------------------
        # 5. Payment details
        # ---------------------------------------------------------

        payment_data = []

        for payment in payments:

            appointment = payment.appointment

            payment_data.append(
                {
                    "reference": (
                        payment.reference
                    ),
                    "appointmentId": (
                        appointment.id
                        if appointment
                        else None
                    ),
                    "client": {
                        "id": (
                            appointment.client_id
                            if appointment
                            else payment.user_id
                        ),
                        "name": (
                            appointment.client.full_name
                            if appointment
                            else payment.user.full_name
                        ),
                    },
                    "nutritionist": {
                        "id": (
                            appointment.nutritionist_id
                            if appointment
                            else None
                        ),
                        "name": (
                            appointment.nutritionist.full_name
                            if appointment
                            else None
                        ),
                    },
                    "amount": float(
                        payment.amount
                    ),
                    "platformFee": float(
                        payment.platform_fee
                    ),
                    "nutritionistAmount": float(
                        payment.nutritionist_amount
                    ),
                    "currency": (
                        payment.currency
                    ),
                    "status": (
                        payment.status
                    ),
                    "starpayOrderId": (
                        payment.starpay_order_id
                    ),
                    "createdAt": (
                        payment.created_at
                    ),
                    "paidAt": payment.paid_at,
                }
            )

        return Response(
            {
                "success": True,
                "summary": {
                    "totalGross": float(
                        total_gross
                    ),
                    "totalPlatformFee": float(
                        total_platform_fee
                    ),
                    "totalNutritionistEarnings": float(
                        total_nutritionist_earnings
                    ),
                    "successfulPayments": (
                        successful_payments.count()
                    ),
                    "currency": "ETB",
                },
                "payments": payment_data,
            }
        )
