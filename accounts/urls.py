from django.conf import settings
from django.contrib.auth import views as auth_views
from django.urls import path

from .views import LoginView, SignupView

app_name = "accounts"

urlpatterns = [
    path("signup/", SignupView.as_view(), name="signup"),
    path("login/", LoginView.as_view(template_name="registration/login.html"), name="login"),
    path("logout/", auth_views.LogoutView.as_view(), name="logout"),
]

if settings.OIDC_ENABLED:
    from mozilla_django_oidc.views import OIDCLogoutView

    # Ends the local session and then the core's (OIDC_OP_LOGOUT_URL_METHOD).
    urlpatterns[-1] = path("logout/", OIDCLogoutView.as_view(), name="logout")
