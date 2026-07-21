from django.urls import path

from . import views

app_name = "leads"

urlpatterns = [
    path("", views.LeadListView.as_view(), name="list"),
    path("export/", views.LeadExportCSVView.as_view(), name="export"),
    path("<int:pk>/", views.LeadDetailView.as_view(), name="detail"),
    path("<int:pk>/status/", views.LeadStatusUpdateView.as_view(), name="update_status"),
]
