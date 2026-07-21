from django.urls import path

from . import views

app_name = "landingpages"

urlpatterns = [
    path("", views.LandingPageListView.as_view(), name="list"),
    path("nova/", views.LandingPageCreateView.as_view(), name="create"),
    path("<int:pk>/editar/", views.LandingPageUpdateView.as_view(), name="edit"),
    path("<int:pk>/publicar/", views.LandingPagePublishView.as_view(), name="publish"),
    path("<int:pk>/despublicar/", views.LandingPageUnpublishView.as_view(), name="unpublish"),
]
