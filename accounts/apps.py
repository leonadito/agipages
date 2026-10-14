from django.apps import AppConfig


class AccountsConfig(AppConfig):
    name = 'accounts'

    def ready(self):
        from . import backchannel  # noqa: F401  (tracks single sign-on sessions at login)
