from django.urls import path

from . import views

app_name = "meta_conversions"

urlpatterns = [
    path("", views.MetaConversionSettingsView.as_view(), name="settings"),
]
