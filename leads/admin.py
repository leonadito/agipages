from django.contrib import admin

from .models import Lead, LeadStatusHistory


class LeadStatusHistoryInline(admin.TabularInline):
    model = LeadStatusHistory
    extra = 0
    readonly_fields = ("old_status", "new_status", "changed_by", "changed_at")
    can_delete = False


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "email", "landing_page", "tenant", "status", "utm_source", "created_at")
    list_filter = ("status", "tenant", "utm_source")
    search_fields = ("name", "email", "phone", "city")
    inlines = [LeadStatusHistoryInline]
