from django.urls import path
from rest_framework_simplejwt.views import (
    TokenObtainPairView,
    TokenRefreshView,
    TokenBlacklistView,
)

from .views import (
    LoginView, RegisterView, MeView, SendOTPView, VerifyOTPView,
    EmailRegisterView,
    SendEmailOTPView, VerifyEmailOTPView, ResetPasswordView,
    StaffApplyView, PendingApplicationsView, ApproveApplicationView, RejectApplicationView,
    ChangePasswordView,CustomTokenObtainPairView
)

urlpatterns = [
    path("register/", RegisterView.as_view(), name="register"),
    path("login/", CustomTokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("token/blacklist/", TokenBlacklistView.as_view(), name="token_blacklist"),  # 👈 JWT logout/revoke

    path("me/", MeView.as_view(), name="me"),
    path("change-password/", ChangePasswordView.as_view(), name="change-password"),
    path("send-otp/", SendOTPView.as_view(), name="send-otp"),
    path("verify-otp/", VerifyOTPView.as_view(), name="verify-otp"),

    path("register-email/", EmailRegisterView.as_view(), name="register-email"),
    path("send-email-otp/", SendEmailOTPView.as_view(), name="send-email-otp"),
    path("verify-email-otp/", VerifyEmailOTPView.as_view(), name="verify-email-otp"),
    path("reset-password/", ResetPasswordView.as_view(), name="reset-password"),

    path("apply-staff/", StaffApplyView.as_view(), name="apply-staff"),
    path("applications/pending/", PendingApplicationsView.as_view(), name="pending-applications"),
    path("applications/<int:application_id>/approve/", ApproveApplicationView.as_view(), name="approve-application"),
    path("applications/<int:application_id>/reject/", RejectApplicationView.as_view(), name="reject-application"),
]
