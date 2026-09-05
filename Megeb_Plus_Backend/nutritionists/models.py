from django.conf import settings
from django.db import models


class NutritionistApplication(models.Model):

    STATUS_CHOICES = [
        ("pending", "Pending"),
        ("approved", "Approved"),
        ("rejected", "Rejected"),
    ]

    AI_STATUS_CHOICES = [
        ("pending", "Pending"),
        ("verified", "Verified"),
        ("failed", "Failed"),
        ("needs_review", "Needs Review"),
    ]
    user = models.OneToOneField(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)

    # Personal information
    full_name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone = models.CharField(max_length=30, unique=True)


    # Professional information
    current_role = models.CharField(max_length=255)
    specialization = models.CharField(max_length=255)
    years_of_experience = models.PositiveIntegerField(default=0)

    # State license
    license_number = models.CharField(
        max_length=255,
        unique=True
    )

    license_jurisdiction = models.CharField(
        max_length=255
    )

    license_expiration_date = models.DateField()

    license_document = models.FileField(
        upload_to="nutritionist_documents/licenses/",
        blank=True,
        null=True
    )

    # National credential
    credential_type = models.CharField(
        max_length=100
    )

    credential_number = models.CharField(
        max_length=255,
        unique=True
    )

    credential_document = models.FileField(
        upload_to="nutritionist_documents/credentials/",
        blank=True,
        null=True
    )

    # Insurance
    insurance_provider = models.CharField(
        max_length=255
    )

    policy_number = models.CharField(
        max_length=255,
        unique=True
    )

    insurance_expiration_date = models.DateField()

    coverage_limit = models.DecimalField(
        max_digits=12,
        decimal_places=2
    )

    insurance_document = models.FileField(
        upload_to="nutritionist_documents/insurance/",
        blank=True,
        null=True
    )

    # Degree
    degree = models.CharField(
        max_length=255
    )

    institution = models.CharField(
        max_length=255
    )

    field_of_study = models.CharField(
        max_length=255
    )

    graduation_year = models.PositiveIntegerField()

    degree_document = models.FileField(
        upload_to="nutritionist_documents/degrees/",
        blank=True,
        null=True
    )

    # AI verification
    ai_status = models.CharField(
        max_length=30,
        choices=AI_STATUS_CHOICES,
        default="pending"
    )

    ai_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True
    )

    ai_result = models.JSONField(
        blank=True,
        null=True
    )

    # Application status
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default="pending"
    )

    rejection_reason = models.TextField(
        blank=True
    )

    submitted_at = models.DateTimeField(
        auto_now_add=True
    )

    reviewed_at = models.DateTimeField(
        blank=True,
        null=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return f"{self.full_name} - {self.license_number}"
    
class NutritionistProfile(models.Model):

    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="nutritionist_profile",
    )

    bio = models.TextField(
        blank=True,
    )

    specialization = models.CharField(
        max_length=255,
        blank=True,
    )

    qualification = models.CharField(
        max_length=255,
        blank=True,
    )

    years_of_experience = models.PositiveIntegerField(
        default=0,
    )

    license_number = models.CharField(
        max_length=255,
        unique=True,
    )

    profile_picture = models.ImageField(
        upload_to="nutritionists/profile/",
        blank=True,
        null=True,
    )

    is_verified = models.BooleanField(
        default=False,
    )

    rating = models.DecimalField(
        max_digits=3,
        decimal_places=2,
        default=0,
    )

    consultation_fee = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=0,
    )

    created_at = models.DateTimeField(
        auto_now_add=True,
    )

    updated_at = models.DateTimeField(
        auto_now=True,
    )

    def __str__(self):
        return self.user.full_name
    
class StateLicense(models.Model):

    application = models.OneToOneField(
        NutritionistApplication,
        on_delete=models.CASCADE,
        related_name="state_license",
    )

    license_number = models.CharField(
        max_length=255,
        unique=True,
    )

    jurisdiction = models.CharField(
        max_length=255,
    )

    expiration_date = models.DateField()

    document = models.FileField(
        upload_to="nutritionist_documents/licenses/"
    )

    # AI verification
    ai_status = models.CharField(
        max_length=30,
        choices=NutritionistApplication.AI_STATUS_CHOICES,
        default="pending",
    )

    ai_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )

    ai_result = models.JSONField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    updated_at = models.DateTimeField(
        auto_now=True
    )

    def __str__(self):
        return self.license_number
    
class NationalCredential(models.Model):

    application = models.OneToOneField(
        NutritionistApplication,
        on_delete=models.CASCADE,
        related_name="national_credential",
    )

    credential_type = models.CharField(
        max_length=255
    )

    credential_number = models.CharField(
        max_length=255,
        unique=True,
    )

    document = models.FileField(
        upload_to="nutritionist_documents/national_credentials/"
    )

    ai_status = models.CharField(
        max_length=30,
        choices=NutritionistApplication.AI_STATUS_CHOICES,
        default="pending",
    )

    ai_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )

    ai_result = models.JSONField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.credential_number
    
class InsuranceCertificate(models.Model):

    application = models.OneToOneField(
        NutritionistApplication,
        on_delete=models.CASCADE,
        related_name="insurance_certificate",
    )

    insurance_provider = models.CharField(
        max_length=255
    )

    policy_number = models.CharField(
        max_length=255,
        unique=True,
    )

    expiration_date = models.DateField()

    coverage_limit = models.DecimalField(
        max_digits=15,
        decimal_places=2
    )

    document = models.FileField(
        upload_to="nutritionist_documents/insurance/"
    )

    ai_status = models.CharField(
        max_length=30,
        choices=NutritionistApplication.AI_STATUS_CHOICES,
        default="pending",
    )

    ai_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )

    ai_result = models.JSONField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return self.policy_number
    
class DegreeCredential(models.Model):

    application = models.OneToOneField(
        NutritionistApplication,
        on_delete=models.CASCADE,
        related_name="degree_credential",
    )

    degree = models.CharField(
        max_length=255
    )

    institution = models.CharField(
        max_length=255
    )

    field_of_study = models.CharField(
        max_length=255
    )

    graduation_year = models.PositiveIntegerField()

    document = models.FileField(
        upload_to="nutritionist_documents/degrees/"
    )

    ai_status = models.CharField(
        max_length=30,
        choices=NutritionistApplication.AI_STATUS_CHOICES,
        default="pending",
    )

    ai_score = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        blank=True,
        null=True,
    )

    ai_result = models.JSONField(
        blank=True,
        null=True,
    )

    created_at = models.DateTimeField(
        auto_now_add=True
    )

    def __str__(self):
        return f"{self.degree} - {self.institution}"