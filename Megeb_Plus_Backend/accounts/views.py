from rest_framework import status, serializers
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework.permissions import IsAuthenticated, BasePermission
from rest_framework.parsers import MultiPartParser, FormParser
from django.contrib.auth import authenticate
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from datetime import timedelta
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User, OTPVerification, PendingRegistration, StaffApplication
from .serializers import (
    RegisterSerializer,
    LoginSerializer,
    UserSerializer,
    SendOTPSerializer,
    EmailRegisterSerializer,
    SendEmailOTPSerializer,
    VerifyEmailOTPSerializer,
    ResetPasswordSerializer,
    StaffApplicationSerializer,
    StaffApplicationListSerializer,
    UpdateProfileSerializer,
    ChangePasswordSerializer,
    CustomTokenObtainPairSerializer
)
from .services.afromessage import send_otp, verify_otp
from .services.email_service import generate_otp, send_otp_email, send_registration_confirmation_email


class CustomTokenObtainPairSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs["identifier"].strip()
        password = attrs["password"]

        user = User.objects.filter(email__iexact=identifier).first()

        if user is None:
            user = User.objects.filter(phone=identifier).first()

        if user is None:
            raise serializers.ValidationError({"detail": "Invalid email/phone or password."})

        if not user.check_password(password):
            raise serializers.ValidationError({"detail": "Invalid email/phone or password."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "This account is inactive."})

        refresh = RefreshToken.for_user(user)
        access_token = refresh.access_token

        # ✅ Add custom claims directly to the token
        access_token["role"] = user.role
        access_token["email"] = user.email
        access_token["phone"] = user.phone
        access_token["full_name"] = user.full_name

        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "role": user.role,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
        }

class CustomTokenObtainPairView(TokenObtainPairView):
    serializer_class = CustomTokenObtainPairSerializer
    
class MeView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UpdateProfileSerializer(request.user, data=request.data, partial=True)

        if serializer.is_valid():
            serializer.save()
            return Response(UserSerializer(request.user).data)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class RegisterView(APIView):

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)

        if serializer.is_valid():
            user = serializer.save()
            return Response(
                {
                    "message": "Registration successful.",
                    "user": {
                        "id": user.id,
                        "full_name": user.full_name,
                        "phone": user.phone,
                        "is_verified": user.is_verified
                    }
                },
                status=status.HTTP_201_CREATED
            )

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class LoginView(APIView):
    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        if serializer.is_valid():
            return Response(serializer.validated_data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)



class SendOTPView(APIView):

    def post(self, request):
        serializer = SendOTPSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        phone = serializer.validated_data["phone"]
        result = send_otp(phone)

        if result.get("acknowledge") != "success":
            return Response(
                {"detail": "Failed to send OTP.", "response": result},
                status=status.HTTP_400_BAD_REQUEST
            )

        verification_id = result["response"]["verificationId"]

        return Response(
            {"message": "OTP sent successfully.", "verificationId": verification_id},
            status=status.HTTP_200_OK
        )


class VerifyOTPView(APIView):

    def post(self, request):
        phone = request.data.get("phone")
        otp = request.data.get("otp")
        verification_id = request.data.get("verificationId")

        if not phone:
            return Response({"detail": "Phone number is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not otp:
            return Response({"detail": "OTP is required."}, status=status.HTTP_400_BAD_REQUEST)

        if not verification_id:
            return Response({"detail": "Verification ID is required."}, status=status.HTTP_400_BAD_REQUEST)

        result = verify_otp(phone, otp, verification_id)

        if result.get("acknowledge") != "success":
            return Response(
                {"detail": "Invalid or expired OTP.", "response": result},
                status=status.HTTP_400_BAD_REQUEST
            )

        return Response({"message": "OTP verified successfully."}, status=status.HTTP_200_OK)


# ---------------------------
# Email flow — user registration (mobile app)
# ---------------------------

class EmailRegisterView(APIView):
    """Step 1: role=user registers with email. Stages in PendingRegistration + sends OTP."""

    def post(self, request):
        serializer = EmailRegisterSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        pending = serializer.save()

        otp = generate_otp()
        OTPVerification.objects.create(
            email=pending.email, otp=otp, channel="email", purpose="registration"
        )
        send_otp_email(pending.email, otp, purpose="registration")

        return Response(
            {"message": "OTP sent to email. Verify to complete registration."},
            status=status.HTTP_200_OK
        )


class SendEmailOTPView(APIView):
    """Send/resend OTP by email — used for registration resend and forgot-password."""

    def post(self, request):
        serializer = SendEmailOTPSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        purpose = serializer.validated_data["purpose"]

        if purpose == "password_reset" and not User.objects.filter(email=email).exists():
            return Response({"detail": "No account found with this email."}, status=status.HTTP_404_NOT_FOUND)

        otp = generate_otp()
        OTPVerification.objects.create(email=email, otp=otp, channel="email", purpose=purpose)
        send_otp_email(email, otp, purpose=purpose)

        return Response({"message": "OTP sent successfully."}, status=status.HTTP_200_OK)


class VerifyEmailOTPView(APIView):
    """Verifies email OTP. If purpose=registration, finalizes PendingRegistration -> User."""

    def post(self, request):
        serializer = VerifyEmailOTPSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        otp = serializer.validated_data["otp"]
        purpose = serializer.validated_data["purpose"]

        record = OTPVerification.objects.filter(
            email=email, otp=otp, channel="email", purpose=purpose, is_verified=False
        ).order_by("-created_at").first()

        if not record:
            return Response({"detail": "Invalid or expired OTP."}, status=status.HTTP_400_BAD_REQUEST)

        if record.created_at < timezone.now() - timedelta(minutes=10):
            return Response({"detail": "OTP has expired."}, status=status.HTTP_400_BAD_REQUEST)

        record.is_verified = True
        record.verified_at = timezone.now()
        record.save()

        if purpose == "registration":
            pending = PendingRegistration.objects.filter(email=email).first()

            if not pending:
                return Response(
                    {"detail": "No pending registration found for this email."},
                    status=status.HTTP_400_BAD_REQUEST
                )

            user = User(
                full_name=pending.full_name,
                email=pending.email,
                role="user",
                is_verified=True,
                is_active=True,
            )
            user.password = pending.password
            user.save()
            pending.delete()

            return Response(
                {
                    "message": "Registration complete.",
                    "user": {
                        "id": user.id,
                        "full_name": user.full_name,
                        "email": user.email,
                        "role": user.role,
                        "is_verified": user.is_verified
                    }
                },
                status=status.HTTP_201_CREATED
            )

        return Response({"message": "OTP verified successfully."}, status=status.HTTP_200_OK)


class ResetPasswordView(APIView):
    """Final step of forgot-password / first-time password setup for approved staff."""

    def post(self, request):
        serializer = ResetPasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        email = serializer.validated_data["email"]
        new_password = serializer.validated_data["new_password"]

        verified_otp = OTPVerification.objects.filter(
            email=email, purpose="password_reset", is_verified=True
        ).order_by("-verified_at").first()

        if not verified_otp or verified_otp.verified_at < timezone.now() - timedelta(minutes=15):
            return Response(
                {"detail": "Please verify OTP again before resetting password."},
                status=status.HTTP_400_BAD_REQUEST
            )

        user = User.objects.filter(email=email).first()
        if not user:
            return Response({"detail": "No account found with this email."}, status=status.HTTP_404_NOT_FOUND)

        user.set_password(new_password)
        user.save()
        verified_otp.delete()

        return Response({"message": "Password reset successful."}, status=status.HTTP_200_OK)


# ---------------------------
# Staff applications — vendor/nutritionist (website), admin review
#
# NOTE: IsAdminRole and _approve_application / _reject_application are
# imported by admin_panel/views.py (AdminNutritionistDetailView reuses this
# same approve/reject logic so the two admin surfaces never drift apart).
# ---------------------------

class IsAdminRole(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.role == "admin")


class StaffApplyView(APIView):
    """Vendor/nutritionist submits an application with documents. No account/password yet."""

    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        serializer = StaffApplicationSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        application = serializer.save()

        send_mail(
            subject="Megeb+ Application Received",
            message=(
                f"Hi {application.full_name},\n\n"
                f"We've received your application to join Megeb+ as a {application.role}.\n"
                f"Our team will review your credentials and get back to you soon."
            ),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[application.email],
            fail_silently=False,
        )

        return Response(
            {
                "message": "Application submitted. You'll be notified by email once reviewed.",
                "application_id": application.id
            },
            status=status.HTTP_201_CREATED
        )


class PendingApplicationsView(APIView):
    """Admin-only: list applications awaiting review."""

    permission_classes = [IsAdminRole]

    def get(self, request):
        applications = StaffApplication.objects.filter(status="pending").order_by("-created_at")
        return Response(StaffApplicationListSerializer(applications, many=True, context={"request": request}).data)


def _approve_application(application, reviewer):
    """Shared logic: approve -> create User with the password set at application time."""
    phone_to_use = application.phone
    if phone_to_use and User.objects.filter(phone=phone_to_use).exists():
        phone_to_use = None

    user = User(
        full_name=application.full_name,
        email=application.email,
        phone=phone_to_use,
        role=application.role,
        is_verified=True,
        is_active=True,
    )
    user.password = application.password  # already hashed
    user.save()

    application.status = "approved"
    application.reviewed_at = timezone.now()
    application.reviewed_by = reviewer
    application.save()

    send_registration_confirmation_email(user.email, user.full_name, user.role)
    return user


def _reject_application(application, reviewer):
    """Shared logic: reject -> notify applicant by email."""
    application.status = "rejected"
    application.reviewed_at = timezone.now()
    application.reviewed_by = reviewer
    application.save()

    send_mail(
        subject="Megeb+ Application Update",
        message=(
            f"Hi {application.full_name},\n\n"
            f"Thank you for applying to Megeb+ as a {application.role}. "
            f"After review, we're unable to approve your application at this time."
        ),
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[application.email],
        fail_silently=False,
    )


class ApproveApplicationView(APIView):
    """Admin-only: approve -> create User with the password they set at application time."""

    permission_classes = [IsAdminRole]

    def post(self, request, application_id):
        application = StaffApplication.objects.filter(id=application_id, status="pending").first()

        if not application:
            return Response({"detail": "Application not found or already reviewed."}, status=status.HTTP_404_NOT_FOUND)

        _approve_application(application, request.user)

        return Response({"message": f"{application.role} approved and account created."}, status=status.HTTP_200_OK)


class RejectApplicationView(APIView):
    """Admin-only: reject -> notify applicant by email."""

    permission_classes = [IsAdminRole]

    def post(self, request, application_id):
        application = StaffApplication.objects.filter(id=application_id, status="pending").first()

        if not application:
            return Response({"detail": "Application not found or already reviewed."}, status=status.HTTP_404_NOT_FOUND)

        _reject_application(application, request.user)

        return Response({"message": "Application rejected and applicant notified."}, status=status.HTTP_200_OK)


# ---------------------------
# Self-service profile & password management
# ---------------------------

class ChangePasswordView(APIView):
    """Authenticated user changes their own password (must know current password)."""

    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = ChangePasswordSerializer(data=request.data)

        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        user = request.user

        if not user.check_password(serializer.validated_data["current_password"]):
            return Response({"detail": "Current password is incorrect."}, status=status.HTTP_400_BAD_REQUEST)

        user.set_password(serializer.validated_data["new_password"])
        user.save()

        return Response({"message": "Password changed successfully."})