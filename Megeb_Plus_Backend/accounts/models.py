from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin, BaseUserManager
from django.db import models


class UserManager(BaseUserManager):
    def create_user(self, phone=None, email=None, password=None, **extra_fields):
        if not phone and not email:
            raise ValueError("Phone or email is required")
        user = self.model(phone=phone, email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, phone, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_active", True)
        return self.create_user(phone=phone, password=password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    ROLE_CHOICES = [
        ("user", "User"),
        ("nutritionist", "Nutritionist"),
        ("admin", "Admin"),
        ("vendor", "Vendor"),
    ]

    id = models.BigAutoField(primary_key=True)

    full_name = models.CharField(max_length=255)

    email = models.EmailField(unique=True, blank=True, null=True)

    phone = models.CharField(
        max_length=20,
        unique=True,
        null=True,
        blank=True
    )

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default="user"
    )

    profile_picture = models.URLField(
        null=True,
        blank=True
    )

    is_verified = models.BooleanField(default=False)

    is_active = models.BooleanField(default=True)

    is_staff = models.BooleanField(default=False)

    created_at = models.DateTimeField(auto_now_add=True)

    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"

    REQUIRED_FIELDS = []

    def __str__(self):
        return self.email or self.phone or str(self.id)


class OTPVerification(models.Model):

    CHANNEL_CHOICES = [
        ("phone", "Phone"),
        ("email", "Email"),
    ]

    PURPOSE_CHOICES = [
        ("registration", "Registration"),
        ("login", "Login"),
        ("password_reset", "Password Reset"),
    ]

    channel = models.CharField(
        max_length=10,
        choices=CHANNEL_CHOICES,
        default="phone"
    )

    phone = models.CharField(max_length=20, null=True, blank=True)
    email = models.EmailField(null=True, blank=True)

    otp = models.CharField(
        max_length=6,
        null=True,
        blank=True
    )

    verification_id = models.CharField(
        max_length=255,
        null=True,
        blank=True
    )

    purpose = models.CharField(
        max_length=30,
        choices=PURPOSE_CHOICES
    )

    is_verified = models.BooleanField(
        default=False
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    verified_at = models.DateTimeField(
        null=True,
        blank=True
    )

    class Meta:
        indexes = [
            models.Index(fields=["phone", "purpose"]),
            models.Index(fields=["email", "purpose"]),
        ]

    def __str__(self):
        identifier = self.phone or self.email
        return f"{identifier} - {self.purpose}"


class PendingRegistration(models.Model):
    full_name = models.CharField(max_length=255)

    phone = models.CharField(max_length=20, unique=True, null=True, blank=True)
    email = models.EmailField(unique=True, null=True, blank=True)

    password = models.CharField(max_length=128)

    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.phone or self.email


class StaffApplication(models.Model):

    ROLE_CHOICES = [
        ("nutritionist", "Nutritionist"),
        ("vendor", "Vendor"),
    ]

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=20, null=True, blank=True)
    password = models.CharField(max_length=128)

    role = models.CharField(max_length=20, choices=ROLE_CHOICES)

    application_data = models.JSONField(default=dict, blank=True)
    # holds text fields: license number, credential type, insurance
    # provider, degree, years of experience, specialization, etc.

    license_document = models.FileField(upload_to="applications/licenses/", null=True, blank=True)
    credential_document = models.FileField(upload_to="applications/credentials/", null=True, blank=True)
    insurance_document = models.FileField(upload_to="applications/insurance/", null=True, blank=True)
    degree_document = models.FileField(upload_to="applications/degrees/", null=True, blank=True)

    status = models.CharField(max_length=10, choices=STATUS_CHOICES, default="pending")

    created_at = models.DateTimeField(auto_now_add=True)
    reviewed_at = models.DateTimeField(null=True, blank=True)
    reviewed_by = models.ForeignKey(
        "User", null=True, blank=True, on_delete=models.SET_NULL, related_name="reviewed_applications"
    )

    def __str__(self):
        return f"{self.full_name} ({self.role}) - {self.status}"
