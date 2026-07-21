from django.contrib import admin

from .models import LandingPage, LandingPageAuditLog, LandingPageGalleryImage


class LandingPageGalleryImageInline(admin.TabularInline):
    model = LandingPageGalleryImage
    extra = 0


class LandingPageAuditLogInline(admin.TabularInline):
    model = LandingPageAuditLog
    extra = 0
    readonly_fields = ("user", "action", "timestamp")
    can_delete = False


@admin.register(LandingPage)
class LandingPageAdmin(admin.ModelAdmin):
    list_display = ("title", "tenant", "status", "slug", "published_at")
    list_filter = ("status", "tenant")
    search_fields = ("title", "slug")
    inlines = [LandingPageGalleryImageInline, LandingPageAuditLogInline]
