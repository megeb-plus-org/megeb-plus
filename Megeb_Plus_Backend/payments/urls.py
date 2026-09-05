
from django.urls import path

from .views import (
    CreatePaymentView,
    PaymentHistoryView,
    PaymentDetailView,
    VerifyPaymentView,
    StarPayCallbackView,
    NutritionistEarningsView,
    AdminPaymentMonitoringView,
)


urlpatterns = [
    path(
        "",
        PaymentHistoryView.as_view(),
        name="payment-history",
    ),

    path(
        "create/",
        CreatePaymentView.as_view(),
        name="create-payment",
    ),

    path(
        "verify/",
        VerifyPaymentView.as_view(),
        name="verify-payment",
    ),

    path(
        "callback/",
        StarPayCallbackView.as_view(),
        name="starpay-callback",
    ),

    path(
        "earnings/",
        NutritionistEarningsView.as_view(),
        name="nutritionist-earnings",
    ),

    path(
        "admin/",
        AdminPaymentMonitoringView.as_view(),
        name="admin-payment-monitoring",
    ),

    path(
        "<str:reference>/",
        PaymentDetailView.as_view(),
        name="payment-detail",
    ),
]

