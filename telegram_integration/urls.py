from django.urls import path

from . import views

app_name = "telegram_integration"

urlpatterns = [
    path("", views.TelegramLinkView.as_view(), name="link"),
]

# Mounted separately (outside the dashboard prefix) in config/urls.py —
# the webhook is a public endpoint Telegram's servers call directly.
webhook_urlpatterns = [
    path("webhook/<str:secret>/", views.TelegramWebhookView.as_view(), name="webhook"),
]
