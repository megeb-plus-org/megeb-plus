from django.urls import path

from .views import (
    NutritionistListView,
    NutritionistApplicationCreateView,
    MyNutritionistApplicationView,
    NutritionistApplicationReviewView,
    NutritionistProfileView,
)
from .views import NutritionistApplicationAIVerifyView


urlpatterns = [

    path(
        "",
        NutritionistListView.as_view(),
        name="nutritionist-list",
    ),

    path(
        "apply/",
        NutritionistApplicationCreateView.as_view(),
        name="nutritionist-apply",
    ),

    path(
        "my-application/",
        MyNutritionistApplicationView.as_view(),
        name="my-nutritionist-application",
    ),

    path(
        "applications/<int:application_id>/review/",
        NutritionistApplicationReviewView.as_view(),
        name="nutritionist-application-review",
    ),

    path(
        "profile/",
        NutritionistProfileView.as_view(),
        name="nutritionist-profile",
    ),
    path(
        "applications/<int:application_id>/ai-verify/",
        NutritionistApplicationAIVerifyView.as_view(),
        name="application-ai-verify",
    ),
]