import json

from django.conf import settings
from django.http import HttpResponse, JsonResponse
from django.shortcuts import render
from django.utils import timezone
from django.utils.decorators import method_decorator
from django.views import View
from django.views.decorators.csrf import csrf_exempt

from core.mixins import TenantDashboardMixin

from .models import TelegramIntegration, TelegramLinkCode
from .services import send_telegram_message


class TelegramLinkView(TenantDashboardMixin, View):
    template_name = "telegram_integration/link.html"

    def get(self, request):
        return self._render(request)

    def post(self, request):
        link_code = TelegramLinkCode.generate_for(self.tenant)
        return self._render(request, link_code=link_code)

    def _render(self, request, link_code=None):
        integration = TelegramIntegration.objects.filter(tenant=self.tenant).first()
        return render(
            request,
            self.template_name,
            {
                "integration": integration,
                "bot_username": settings.TELEGRAM_BOT_USERNAME,
                "link_code": link_code,
            },
        )


@method_decorator(csrf_exempt, name="dispatch")
class TelegramWebhookView(View):
    """Receives Telegram Bot API updates. Telegram can't sign requests, so
    the path itself carries a random secret (TELEGRAM_WEBHOOK_SECRET) —
    anything else is rejected as if the route didn't exist."""

    def post(self, request, secret):
        if not settings.TELEGRAM_WEBHOOK_SECRET or secret != settings.TELEGRAM_WEBHOOK_SECRET:
            return HttpResponse(status=404)

        try:
            payload = json.loads(request.body.decode("utf-8"))
        except (ValueError, UnicodeDecodeError):
            return HttpResponse(status=400)

        message = payload.get("message") or {}
        text = (message.get("text") or "").strip()
        chat = message.get("chat") or {}
        chat_id = chat.get("id")

        if chat_id is not None and text.startswith("/start"):
            parts = text.split(maxsplit=1)
            code = parts[1].strip() if len(parts) > 1 else ""
            self._handle_start(code, chat_id)

        return JsonResponse({"ok": True})

    def _handle_start(self, code, chat_id):
        try:
            link_code = TelegramLinkCode.objects.get(code=code)
        except TelegramLinkCode.DoesNotExist:
            send_telegram_message(chat_id, "Código inválido. Gere um novo link no painel.")
            return

        if not link_code.is_valid():
            send_telegram_message(chat_id, "Código expirado. Gere um novo link no painel.")
            return

        TelegramIntegration.objects.update_or_create(
            tenant=link_code.tenant,
            defaults={
                "chat_id": str(chat_id),
                "is_active": True,
                "linked_at": timezone.now(),
            },
        )
        link_code.used = True
        link_code.save(update_fields=["used"])
        send_telegram_message(
            chat_id,
            "Conta vinculada com sucesso! Você vai receber por aqui as notificações "
            "de novos leads.",
        )
