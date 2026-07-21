# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this system is

A multi-tenant SaaS where real-estate agents/agencies build lead-capture landing pages for property launches via a structured form (no code/designer needed), then manage received leads in a dashboard with real-time Telegram notifications. Full spec in `PRD.md` (Portuguese) — read it for anything not covered here. `landing-page-exemplo.png` is the visual reference the public template follows; `diamond-infinity-towers/` holds real sample content used to seed a demo tenant.

The MVP (all 7 milestones below) is implemented. Commit history (`git log --oneline`) maps 1:1 to these milestones if you need the order things were built in.

## Commands

```bash
# Activate the venv first (Python 3.12; created via `py -3.12 -m venv .venv`)
source .venv/Scripts/activate        # git-bash/WSL
# .venv\Scripts\Activate.ps1         # PowerShell

python manage.py runserver           # dev server, http://127.0.0.1:8000
python manage.py test                # full suite
python manage.py test leads          # single app
python manage.py test leads.tests.LeadDashboardTests.test_filter_by_status  # single test

python manage.py makemigrations && python manage.py migrate
python manage.py createsuperuser
python manage.py seed_diamond_tenant # demo tenant + published landing page from diamond-infinity-towers/ assets
python manage.py generate_traefik_config  # force-regenerate traefik/dynamic/tenants.yml (also runs automatically via a Tenant post_save/post_delete signal)

# Tailwind (run from frontend/, or --prefix from repo root)
npm --prefix frontend run build:css  # one-off build → static/css/tailwind.css
npm --prefix frontend run watch:css  # rebuild on change during dev
```

`DJANGO_SETTINGS_MODULE` defaults to `config.settings.dev` (set in `manage.py`); production uses `config.settings.prod` (set explicitly by `docker-compose.yml`). Both read secrets/config from `.env` via `django-environ` — copy `.env.example` to `.env` for local dev (never commit `.env`; it's gitignored and holds real secrets like `TELEGRAM_BOT_TOKEN`).

There is no Docker available in this dev environment, so `docker build`/`docker-compose up` have not been run here — only validated by static review (YAML parses, Dockerfile read-through). Test that flow for real before relying on it in production.

## Architecture

Flat app layout at repo root (no `apps/` wrapper): `config/` (settings package + urls), `tenants/`, `accounts/`, `core/`, `landingpages/`, `leads/`, `telegram_integration/`. Templates live under one root `templates/` dir (not per-app), mirroring app names (`templates/landingpages/`, `templates/leads/`, etc.), plus `templates/public/` for the public site and `templates/registration/` for auth.

### Multi-tenancy — the load-bearing design decision

`accounts.User` is a custom user model (`AUTH_USER_MODEL`, email-based login, no `username` field) with a nullable FK to `tenants.Tenant`. **Every dashboard view must inherit `core.mixins.TenantDashboardMixin`**, which sets `self.tenant = request.user.tenant` in `dispatch()` and adds it to template context — dashboard code must filter every queryset by `self.tenant`, never by a bare ID or URL segment. This is the single most important invariant in the codebase (PRD §8): a `landingpages:edit` or `leads:detail` request for another tenant's object must 404, not leak data. See the tenant-isolation tests in `landingpages/tests.py`, `leads/tests.py` for the pattern (create two tenants, assert cross-tenant access 404s).

The public site is the one place a URL segment IS allowed to resolve a tenant (`landingpages.views._resolve_public_tenant`) — because it's the routing mechanism for a page that's intentionally public. `tenants/middleware.py::TenantResolutionMiddleware` sets `request.tenant` from the `Host` header when it matches a verified `Tenant.custom_domain`, and additionally swaps `request.urlconf` to `config.urls_custom_domain` (which only defines the public-page route — no dashboard/admin/accounts reachable through a tenant's custom domain, a second structural layer of isolation on top of the view-level checks). When the host doesn't match any verified domain, `request.tenant` stays `None` and `landingpages.views.public_page` resolves the tenant from the `<tenant_slug>` path segment instead (the `meusaas.com/<tenant-slug>/<page-slug>/` fallback). Both URL forms hit the *same* view function for both GET (render) and POST (HTMX lead submission).

### Landing pages (`landingpages/`)

`LandingPage` is one wide model covering all 10 fixed template sections (hero, faixa de destaque, condições financeiras, formulário de captura, vídeo institucional, requisitos, características, orçamento, CTA final + rodapé — see PRD §5 for the exact field list per section), plus `LandingPageGalleryImage` (ordered, FK'd) and `LandingPageAuditLog` (who created/updated/published/unpublished, when — PRD §8 auditability). Slug is auto-generated from title and **locked forever once `published_at` is ever set** (`LandingPage.save()` enforces this by re-reading the DB row), so a published public URL never breaks even if the page is later unpublished and edited again. Publishing is blocked (see `landingpages/forms.py::get_publish_errors`) until a minimum set of fields + at least one gallery image exist.

The create/edit form (`templates/landingpages/form.html`) is a single real Django form + an `inlineformset_factory` for gallery images, with Alpine.js doing purely client-side tab switching across the 10 sections (`x-show`, no server round-trip per tab) — there's no server-side wizard.

### Public site + leads (`landingpages/views.py::public_page`, `leads/`)

Draft pages 404 on both URL forms — only `status=LandingPage.PUBLISHED` is ever served. UTM params (+`gclid`/`fbclid`) are read from the query string on GET and re-emitted as hidden inputs in the lead form, so they travel with the HTMX POST without needing session storage. Facebook Pixel / Google Ads snippets are injected per-landing-page (not per-tenant), only when that page's IDs are set. The lead form POSTs to `request.path` (the same URL) via `hx-post`/`hx-target`, swapping in either `public/partials/lead_form_success.html` or a re-rendered `lead_form.html` with errors — no page reload. Anti-spam is a honeypot field (`leads/forms.py::LeadCaptureForm.clean_website`) plus `django-ratelimit` (`method="POST"` only, so GET traffic from ads is never rate-limited).

`Lead` creation fires a `post_save` signal — but the receiver lives in `telegram_integration/signals.py`, not in `leads/`, connected via `telegram_integration/apps.py::ready()`. This keeps `leads` decoupled from the notification mechanism entirely.

### Leads dashboard (`leads/`)

`leads/filters.py::LeadFilter` (django-filter) is shared between the HTML list view and the CSV export (`leads/views.py::LeadExportCSVView`, streamed via `StreamingHttpResponse` + `csv.writer`) specifically so they can never drift out of sync. The `landing_page` filter's queryset is always restricted to the current tenant in `LeadFilter.__init__`, and the base queryset passed in is *also* pre-filtered by tenant — double protection against a crafted `?landing_page=<other tenant's id>`. Status changes are inline HTMX posts that also write a `LeadStatusHistory` row (who/when).

### Telegram integration (`telegram_integration/`)

Linking a tenant's Telegram chat requires an inbound webhook (Telegram never exposes a user's `chat_id` any other way) — `TelegramWebhookView` at `/telegram/webhook/<secret>/`, where `<secret>` is compared against `TELEGRAM_WEBHOOK_SECRET` since Telegram doesn't sign requests. The dashboard generates a short-lived `TelegramLinkCode` and shows a `t.me/<bot>?start=<code>` deep link; tapping it sends `/start <code>` to the bot, which the webhook exchanges for an activated `TelegramIntegration(chat_id=...)`. `telegram_integration/services.py::send_telegram_message` wraps the actual HTTP call in `try/except` with a short timeout — a Telegram failure must never surface to the visitor who just submitted the public lead form, since the `Lead` is already committed before this runs (PRD §7.7). This is proven directly in `telegram_integration/tests.py` by mocking `requests.post` to raise `Timeout` and asserting the `Lead` still gets created.

Real end-to-end testing (actual bot + public webhook URL) needs a public HTTPS endpoint — Telegram's servers can't reach `127.0.0.1`. This wasn't exercised against production; do it against the real deployed domain (see Docker/Traefik below) rather than fighting with a tunnel tool locally.

### Docker / Traefik / custom domains (untested locally — no Docker available in this dev environment)

`Dockerfile` is a 2-stage build (Node stage compiles Tailwind → `static/css/tailwind.css`; Python stage runs `collectstatic` and serves via `gunicorn`). `docker-compose.yml` runs `web` (no published ports — reachable only via the `traefik` docker network) and `traefik`. Per-tenant custom domain routing uses Traefik's **file provider**, not Docker labels: `tenants/traefik.py::regenerate_traefik_config()` rewrites `traefik/dynamic/tenants.yml` (gitignored, generated) with one router per verified `Tenant.custom_domain`, all pointing at the same statically-defined `web` service (declared once in the tracked `traefik/dynamic/platform.yml`, which also declares the platform's own fallback-domain router — replace `meusaas.example.com` in that file with the real platform domain before deploying). Regeneration is wired to a `post_save`/`post_delete` signal on `Tenant` (`tenants/signals.py`) so a domain going from unverified → verified takes effect without restarting the stack, per PRD §9. There's no domain-verification UI/flow built yet (DNS TXT-record proof of ownership was the intended design, per the original plan) — `Tenant.domain_verified` currently has to be flipped manually (e.g. via `/admin/`).

SQLite lives on a named volume (`sqlite_data:/data`, path driven by `DATABASE_PATH` env var) and uploaded media on another (`media_data:/app/media`) — both because the container filesystem itself is ephemeral.
