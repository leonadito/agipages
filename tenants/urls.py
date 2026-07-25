from django.urls import path

from . import views

app_name = "tenants"

urlpatterns = [
    path("", views.DomainSettingsView.as_view(), name="domain"),
    path("verificar/", views.DomainVerifyView.as_view(), name="domain_verify"),
]
