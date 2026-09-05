import random
from django.core.mail import send_mail
from django.conf import settings


def generate_otp():
    return str(random.randint(100000, 999999))


def send_otp_email(email, otp, purpose="registration"):
    """
    purpose: 'registration' or 'password_reset'
    """
    if purpose == "registration":
        subject = "Verify your Megeb+ account"
        message = f"Your Megeb+ verification code is: {otp}\n\nThis code expires in 10 minutes."
    else:
        subject = "Reset your Megeb+ password"
        message = f"Your password reset code is: {otp}\n\nThis code expires in 10 minutes. If you didn't request this, ignore this email."

    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


def send_registration_confirmation_email(email, full_name, role):
    subject = "Welcome to Megeb+"
    message = (
        f"Hi {full_name},\n\n"
        f"Your Megeb+ account has been registered successfully as a {role}.\n"
        f"You can now log in and get started."
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )