from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.http import JsonResponse
from django.urls import include, path


def home(request):
    return JsonResponse({
        "message": "MegebPlus API is running",
        "status": "success"
    })


urlpatterns = [
    path("", home),

    path("admin/", admin.site.urls),

    path(
        "api/appointments/",
        include("appointments.urls")
    ),

    path(
        "api/nutritionists/",
        include("nutritionists.urls")
    ),

    path(
        "api/chat/",
        include("chat.urls")
    ),

    path(
        "api/auth/",
        include("accounts.urls")
    ),

    path(
        "api/health/",
        include("health.urls")
    ),

    path(
        "api/auth/admin/",
        include("admin_panel.urls")
    ),

    path(
        "api/payments/",
        include("payments.urls")
    ),
] + static(
    settings.MEDIA_URL,
    document_root=settings.MEDIA_ROOT
)
