from django.contrib import admin

from .models import NotificationLog, Order, OrderItem, OrderTrackingEvent, Payment, ReturnRequest


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ("order_number", "user", "status", "settlement_status", "grand_total", "currency", "created_at")
    list_filter = ("status", "currency")
    search_fields = ("order_number", "user__email")
    inlines = [OrderItemInline]


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("order", "provider", "transaction_id", "status", "amount")
    list_filter = ("provider", "status")


@admin.register(OrderTrackingEvent)
class OrderTrackingEventAdmin(admin.ModelAdmin):
    list_display = ("order", "event_type", "title", "location", "occurred_at")
    list_filter = ("event_type",)
    search_fields = ("order__order_number", "title", "description", "location")


@admin.register(ReturnRequest)
class ReturnRequestAdmin(admin.ModelAdmin):
    list_display = ("order", "order_item", "status", "requested_at", "processed_at")
    list_filter = ("status",)
    search_fields = ("order__order_number", "reason", "details")


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ("order", "recipient", "channel", "status", "delivered_at", "created_at")
    list_filter = ("channel", "status")
    search_fields = ("order__order_number", "recipient__email", "subject", "message", "provider_reference")
