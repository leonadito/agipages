# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state of this repository

**There is no application code here yet.** This directory currently contains only planning/reference material:

- `PRD.md` — the full product spec (in Portuguese). This is the source of truth for scope, data model, and technical decisions. Read it before proposing or building anything.
- `landing-page-exemplo.png` — a reference screenshot of the layout the public landing page template should follow (see PRD section 5, "Anatomia da landing page").
- `diamond-infinity-towers/` — real content for the first landing page to be built with this system, used as sample data/assets, not code:
  - `folder-infinity-OF.pdf`, `diamond-infinity-condicoes-pagamento.jpeg` — property/financing content for the "Condições financeiras" and "Requisitos" sections.
  - `diamond-infinity-towers_imagens-empreendimento/` — gallery images for the "Galeria/carrossel" section.
  - `albertokappel_criativo_*.png`, `kappel_exemplos-criativos/` — ad creatives (Facebook/Instagram style), useful as reference for hero imagery and tone, not for the app UI itself.

There is no `manage.py`, no `docker-compose.yml`, no package manifest, and no git repository initialized yet (`git init` has not been run). Do not assume a project skeleton exists — check before referencing paths like `manage.py` or app directories, since they don't exist yet.

Since there's no code, there are no build/lint/test commands to run. When implementation starts, this section should be updated with the real commands (`python manage.py runserver`, `python manage.py test`, etc.).

## What this system is (from PRD.md)

A multi-tenant SaaS where real-estate agents/agencies build lead-capture landing pages for property launches via a structured form (no code/designer needed), then manage received leads in a dashboard with real-time Telegram notifications.

Key domain rules to keep in mind for any future implementation work (see `PRD.md` for full detail — section numbers below refer to it):

- **Multi-tenancy isolation is the top security concern (§7.1, §8):** every `Lead`/`LandingPage` query must filter by the tenant from the authenticated session — never infer tenant from a URL segment. The public site's tenant slug in the URL is routing only, and must never be trusted by the admin dashboard.
- **Custom domain is configured per-tenant, not per-landing-page (§7.3):** a single tenant-resolution middleware must handle both cases — resolving tenant from the `Host` header (custom domain) or from the first path segment (fallback `meusaas.com/<tenant-slug>/<page-slug>`). Publishing a landing page never depends on a domain being configured.
- **Draft vs. Published:** a landing page is only publicly reachable (either URL form) once published.
- **Tracking IDs (Facebook Pixel / Google Ads) are per-landing-page, not per-tenant/domain (§7.4)** — the same client may run different campaigns with different pixels across pages on the same domain.
- **Telegram notification is synchronous with a short timeout and silent failure (§7.7, §9):** the lead must already be saved before the Telegram call; a notification failure must never block the success response to the visitor. No task queue in the MVP — only reconsider Celery/RQ if lead volume demands it.
- **LGPD/consent is explicitly out of MVP scope but flagged as a pre-production blocker (§9)** — don't silently add compliance UI, but don't treat it as fully resolved either if asked about production readiness.

## Planned stack (PRD §10 — not yet implemented)

- **Backend:** Python/Django.
- **Frontend:** Django Templates + HTMX (server-driven interactivity) + Alpine.js (light client-side state) + Tailwind CSS. No SPA/heavy JS framework.
- **Database:** SQLite initially, on a persistent Docker volume (not container-ephemeral filesystem); migrate to Postgres only when concurrent-write/scale needs justify it.
- **Media storage:** Docker volume/bind mount in dev; S3-compatible object storage in production.
- **Infra:** Dockerized app behind a reverse proxy (Traefik or Caddy) doing automatic ACME/SSL issuance per verified tenant domain, driven by Docker provider/labels or dynamic config (no stack restart needed to add a domain).
- **Notifications:** synchronous HTTP call to Telegram Bot API, short timeout, try/except swallow on failure.

## Data model (high level, PRD §11)

`Tenant` (slug, custom_domain, domain_verified) → 1:N `User`, 1:N `LandingPage`. `LandingPage` (10 content sections + status + slug + pixel/ads IDs) → 1:N `Lead` (form data + UTM + status + timestamps) → 1:N `LeadStatusHistory`. `Tenant` → 1:1 `TelegramIntegration` (chat_id).

The landing page template has exactly 10 fixed sections (hero, faixa de destaque, galeria, condições financeiras, formulário de captura, vídeo institucional, requisitos, características do imóvel, orçamento/oportunidade, CTA final + rodapé) — see PRD §5 for the full field list per section. The MVP is a single template for real estate; no drag-and-drop builder, no multi-vertical templates.
