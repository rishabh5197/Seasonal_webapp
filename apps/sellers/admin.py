from django.contrib import admin

from .models import SellerProfile


@admin.register(SellerProfile)
class SellerProfileAdmin(admin.ModelAdmin):
    list_display = ("business_name", "user", "status", "approved_at", "created_at")
    list_filter = ("status",)
    search_fields = ("business_name", "display_name", "user__email")

    @admin.action(description="Approve selected sellers")
    def approve_sellers(self, request, queryset):  # noqa: ARG002
        queryset.update(status=SellerProfile.Status.APPROVED)

    @admin.action(description="Decline selected sellers")
    def decline_sellers(self, request, queryset):  # noqa: ARG002
        queryset.update(status=SellerProfile.Status.REJECTED)

    actions = [approve_sellers, decline_sellers]
