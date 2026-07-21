from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ("name", "slug", "custom_domain", "domain_verified", "created_at")
    prepopulated_fields = {"slug": ("name",)}
    search_fields = ("name", "slug", "custom_domain")
