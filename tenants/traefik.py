"""Generates traefik/dynamic/tenants.yml — routers for every verified
tenant custom domain, all pointing at the same `web` service (defined
once, statically, in traefik/dynamic/platform.yml).

Each verified apex domain also gets a `www.<domain>` router that redirects
to it (a plain `redirectRegex` middleware), so a tenant's domain works both
with and without "www" the moment it's verified — this used to require a
manual, per-tenant addition to the infra repo's platform.yml (see the
albertokappel/drasofiaferrao history) until this was automated.

Traefik's file provider runs with `watch: true` (see traefik/traefik.yml),
so rewriting this file is picked up automatically — no stack restart
needed when a tenant's domain gets verified/unverified (PRD §9).
"""
import re
import sys
from pathlib import Path

import yaml
from django.conf import settings

DYNAMIC_CONFIG_PATH = Path(settings.BASE_DIR) / "traefik" / "dynamic" / "tenants.yml"

# This path is a fixed, real host location (bind-mounted, per docker-compose.yml)
# regardless of which database wrote to it — it's the SAME file whether a
# Tenant save happened against the real DB or against `manage.py test`'s
# throwaway in-memory one. Without this guard, running the test suite (which
# creates/deletes many Tenant rows via the post_save/post_delete signal in
# tenants/signals.py) overwrites the real production Traefik routing config
# with whatever test data happened to exist when the last Tenant was
# touched — this has actually happened, silently breaking every verified
# tenant's custom domain until someone reruns `generate_traefik_config`.
_RUNNING_TESTS = "test" in sys.argv[1:2]


def build_traefik_dynamic_config():
    from .models import Tenant

    routers = {}
    middlewares = {}
    verified_tenants = Tenant.objects.filter(domain_verified=True).exclude(custom_domain="")
    for tenant in verified_tenants:
        domain = tenant.custom_domain
        router_name = f"tenant-{tenant.slug}"
        rule = f"Host(`{domain}`)"
        routers[f"{router_name}-websecure"] = {
            "rule": rule,
            "service": "web",
            "entryPoints": ["websecure"],
            "tls": {"certResolver": "letsencrypt"},
        }
        routers[f"{router_name}-web"] = {
            "rule": rule,
            "service": "web",
            "entryPoints": ["web"],
        }

        # Every verified apex also gets a working www companion that
        # redirects to it, so a tenant never has to know "www doesn't
        # work" is even a thing that used to require a manual router in
        # the infra repo's platform.yml (see albertokappel/drasofiaferrao
        # history). Skipped when the tenant registered "www.something" as
        # their own custom_domain — "www.www...." would be nonsense.
        if not domain.startswith("www."):
            www_domain = f"www.{domain}"
            www_rule = f"Host(`{www_domain}`)"
            middleware_name = f"{router_name}-www-to-apex"
            middlewares[middleware_name] = {
                "redirectRegex": {
                    "regex": f"^https?://{re.escape(www_domain)}/(.*)",
                    "replacement": f"https://{domain}/${{1}}",
                    "permanent": True,
                }
            }
            routers[f"{router_name}-www-websecure"] = {
                "rule": www_rule,
                "service": "web",
                "entryPoints": ["websecure"],
                "tls": {"certResolver": "letsencrypt"},
                "middlewares": [middleware_name],
            }
            routers[f"{router_name}-www-web"] = {
                "rule": www_rule,
                "service": "web",
                "entryPoints": ["web"],
                "middlewares": [middleware_name],
            }
    return {"http": {"routers": routers, "middlewares": middlewares}}


def regenerate_traefik_config():
    if _RUNNING_TESTS:
        return None
    config = build_traefik_dynamic_config()
    DYNAMIC_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DYNAMIC_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return DYNAMIC_CONFIG_PATH
