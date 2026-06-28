from django.contrib import admin

from .models import CommercePolicy, HomepageBanner


@admin.register(CommercePolicy)
class CommercePolicyAdmin(admin.ModelAdmin):
    list_display = (
        "shipping_fee_amount",
        "premium_free_shipping_threshold",
        "non_premium_free_shipping_threshold",
        "premium_membership_annual_fee",
        "premium_membership_duration_days",
        "is_active",
        "created_at",
    )
    list_filter = ("is_active",)
    ordering = ("-is_active", "-created_at")
    fieldsets = (
        ("Shipping rules", {"fields": ("shipping_fee_amount", "premium_free_shipping_threshold", "non_premium_free_shipping_threshold")}),
        ("Premium membership", {"fields": ("premium_membership_annual_fee", "premium_membership_duration_days")}),
        ("Status", {"fields": ("is_active",)}),
    )


@admin.register(HomepageBanner)
class HomepageBannerAdmin(admin.ModelAdmin):
    list_display = ("title", "badge", "is_active", "sort_order", "start_at", "end_at")
    list_filter = ("is_active", "accent")
    search_fields = ("title", "subtitle", "badge")
    ordering = ("sort_order", "-created_at")
