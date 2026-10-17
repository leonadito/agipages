from .base import *  # noqa: F401,F403

DEBUG = False

SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

# Traefik (network_mode: host) reaches the container through the published
# 127.0.0.1 port, so requests arrive from the Docker bridge gateway
# (172.16.0.0/12 covers Docker's default bridge pools).
TRUSTED_PROXY_CIDRS = env.list("TRUSTED_PROXY_CIDRS", default=["172.16.0.0/12"])
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
