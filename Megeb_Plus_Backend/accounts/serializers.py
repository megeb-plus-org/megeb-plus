from rest_framework import serializers
from django.contrib.auth.hashers import make_password
from .models import User, PendingRegistration, StaffApplication
from django.contrib.auth import authenticate
from django.db.models import Q
from rest_framework_simplejwt.serializers import RefreshToken, TokenObtainPairSerializer 
from .models import User


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = [
            "id",
            "full_name",
            "email",
            "phone",
            "role",
            "profile_picture",
            "is_verified",
        ]


class RegisterSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    confirm_password = serializers.CharField(
        write_only=True
    )
    email = serializers.EmailField(required=False, allow_null=True)
    phone = serializers.CharField(required=False, allow_null=True)

    class Meta:
        model = User
        fields = [
            "full_name",
            "phone",
            "email",
            "password",
            "confirm_password"
        ]

    def validate(self, data):

        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })
        if not data.get("phone") and not data.get("email"):
            raise serializers.ValidationError({"detail": "Either phone or email is required."})

        return data

    def create(self, validated_data):

        validated_data.pop("confirm_password")

        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        return user

    def create(self, validated_data):

        validated_data.pop("confirm_password")

        password = validated_data.pop("password")

        user = User.objects.create_user(
            password=password,
            **validated_data
        )

        return user
class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        identifier = attrs.get("identifier")
        password = attrs.get("password")

        # Find user by email OR phone
        user = User.objects.filter(Q(email=identifier) | Q(phone=identifier)).first()
        
        if not user or not user.check_password(password):
            raise serializers.ValidationError({"detail": "Invalid credentials."})

        if not user.is_active:
            raise serializers.ValidationError({"detail": "This account is inactive."})

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)
        return {
            "refresh": str(refresh),
            "access": str(refresh.access_token),
            "role": user.role,
            "full_name": user.full_name,
            "email": user.email,
            "phone": user.phone,
        }

class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):
    def validate(self, attrs):
        data = super().validate(attrs)
        # Add extra claims to the response body
        data['user_id'] = self.user.id
        data['role'] = self.user.role
        data['email'] = self.user.email
        data['phone'] = self.user.phone
        return data

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Add extra claims inside the JWT payload itself
        token['role'] = user.role
        token['email'] = user.email
        token['phone'] = user.phone
        return token

class PendingRegistrationSerializer(serializers.ModelSerializer):

    password = serializers.CharField(
        write_only=True,
        min_length=8
    )

    confirm_password = serializers.CharField(
        write_only=True
    )

    class Meta:
        model = PendingRegistration
        fields = [
            "full_name",
            "phone",
            "password",
            "confirm_password",
        ]

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({
                "confirm_password": "Passwords do not match."
            })

        if User.objects.filter(phone=data["phone"]).exists():
            raise serializers.ValidationError({
                "phone": "This phone number is already registered."
            })

        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password")

        password = validated_data.pop("password")

        validated_data["password"] = make_password(password)

        return PendingRegistration.objects.create(
            **validated_data
        )


class SendOTPSerializer(serializers.Serializer):
    phone = serializers.CharField()


# ---------------------------
# Email flow — user registration (mobile app)
# ---------------------------

class EmailRegisterSerializer(serializers.ModelSerializer):
    """Step 1: role=user registers with email. Stages in PendingRegistration."""

    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = PendingRegistration
        fields = ["full_name", "email", "password", "confirm_password"]

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})

        PendingRegistration.objects.filter(email=data["email"]).delete()

        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")
        validated_data["password"] = make_password(password)
        return PendingRegistration.objects.create(**validated_data)


class SendEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    purpose = serializers.ChoiceField(choices=["registration", "password_reset"], default="registration")


class VerifyEmailOTPSerializer(serializers.Serializer):
    email = serializers.EmailField()
    otp = serializers.CharField()
    purpose = serializers.ChoiceField(choices=["registration", "password_reset"], default="registration")


class ResetPasswordSerializer(serializers.Serializer):
    email = serializers.EmailField()
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_new_password"]:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})
        return data


# ---------------------------
# Staff applications — vendor/nutritionist (website), admin review
# ---------------------------

class StaffApplicationSerializer(serializers.ModelSerializer):
    """Vendor/nutritionist submits an application with documents + password."""

    password = serializers.CharField(write_only=True, min_length=8)
    confirm_password = serializers.CharField(write_only=True)

    class Meta:
        model = StaffApplication
        fields = [
            "full_name", "email", "phone", "role", "password", "confirm_password", "application_data",
            "license_document", "credential_document", "insurance_document", "degree_document",
        ]

    def validate(self, data):
        if data["password"] != data["confirm_password"]:
            raise serializers.ValidationError({"confirm_password": "Passwords do not match."})

        if data["role"] not in ["nutritionist", "vendor"]:
            raise serializers.ValidationError({"role": "Role must be nutritionist or vendor."})

        if User.objects.filter(email=data["email"]).exists():
            raise serializers.ValidationError({"email": "This email is already registered."})

        if StaffApplication.objects.filter(email=data["email"], status="pending").exists():
            raise serializers.ValidationError({"email": "An application with this email is already pending."})

        return data

    def create(self, validated_data):
        validated_data.pop("confirm_password")
        password = validated_data.pop("password")
        validated_data["password"] = make_password(password)
        return StaffApplication.objects.create(**validated_data)


class StaffApplicationListSerializer(serializers.ModelSerializer):
    """For admin to view pending applications."""

    class Meta:
        model = StaffApplication
        fields = [
            "id", "full_name", "email", "phone", "role", "application_data",
            "license_document", "credential_document", "insurance_document", "degree_document",
            "status", "created_at",
        ]

# ---------------------------
# Self-service profile & password management
# ---------------------------

class UpdateProfileSerializer(serializers.ModelSerializer):
    """
    Lets a logged-in user update their own basic profile fields.
    Email is deliberately excluded — it's the login identifier (USERNAME_FIELD),
    so changing it needs its own OTP-verified flow, not a plain field edit.
    """

    class Meta:
        model = User
        fields = ["full_name", "phone", "profile_picture"]

    def validate_phone(self, value):
        if value and User.objects.exclude(id=self.instance.id).filter(phone=value).exists():
            raise serializers.ValidationError("This phone number is already in use.")
        return value


class ChangePasswordSerializer(serializers.Serializer):
    current_password = serializers.CharField(write_only=True)
    new_password = serializers.CharField(write_only=True, min_length=8)
    confirm_new_password = serializers.CharField(write_only=True)

    def validate(self, data):
        if data["new_password"] != data["confirm_new_password"]:
            raise serializers.ValidationError({"confirm_new_password": "Passwords do not match."})
        return data
