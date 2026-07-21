"""Generates traefik/dynamic/tenants.yml — one HTTP router per verified
tenant custom domain, all pointing at the same `web` service (defined
once, statically, in traefik/dynamic/platform.yml).

Traefik's file provider runs with `watch: true` (see traefik/traefik.yml),
so rewriting this file is picked up automatically — no stack restart
needed when a tenant's domain gets verified/unverified (PRD §9).
"""
from pathlib import Path

import yaml
from django.conf import settings

DYNAMIC_CONFIG_PATH = Path(settings.BASE_DIR) / "traefik" / "dynamic" / "tenants.yml"


def build_traefik_dynamic_config():
    from .models import Tenant

    routers = {}
    verified_tenants = Tenant.objects.filter(domain_verified=True).exclude(custom_domain="")
    for tenant in verified_tenants:
        router_name = f"tenant-{tenant.slug}"
        rule = f"Host(`{tenant.custom_domain}`)"
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
    return {"http": {"routers": routers}}


def regenerate_traefik_config():
    config = build_traefik_dynamic_config()
    DYNAMIC_CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(DYNAMIC_CONFIG_PATH, "w", encoding="utf-8") as f:
        yaml.safe_dump(config, f, sort_keys=False)
    return DYNAMIC_CONFIG_PATH
