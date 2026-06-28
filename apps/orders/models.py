from django.conf import settings
from django.db import models
from django.utils import timezone
from datetime import timedelta

from apps.accounts.models import Address
from apps.catalog.models import Product
from apps.core.models import BaseModel


class Order(BaseModel):
    class Status(models.TextChoices):
        PENDING = "pending", "Pending"
        CONFIRMED = "confirmed", "Confirmed"
        PACKED = "packed", "Packed"
        SHIPPED = "shipped", "Shipped"
        DELIVERED = "delivered", "Delivered"
        CANCELLED = "cancelled", "Cancelled"
        RETURNED = "returned", "Returned"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="orders")
    order_number = models.CharField(max_length=32, unique=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING)
    shipping_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="shipping_orders")
    billing_address = models.ForeignKey(Address, on_delete=models.SET_NULL, null=True, blank=True, related_name="billing_orders")
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    shipping_fee = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    tax_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    discount_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    grand_total = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    currency = models.CharField(max_length=12, default="INR")
    notes = models.TextField(blank=True)
    tracking_number = models.CharField(max_length=64, unique=True, blank=True)
    placed_at = models.DateTimeField(null=True, blank=True)
    confirmed_at = models.DateTimeField(null=True, blank=True)
    packed_at = models.DateTimeField(null=True, blank=True)
    shipped_at = models.DateTimeField(null=True, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    return_window_ends_at = models.DateTimeField(null=True, blank=True)
    seller_settlement_at = models.DateTimeField(null=True, blank=True)
    seller_settled_at = models.DateTimeField(null=True, blank=True)

    class SettlementStatus(models.TextChoices):
        HOLD = "hold", "Hold"
        ELIGIBLE = "eligible", "Eligible"
        RELEASED = "released", "Released"

    settlement_status = models.CharField(max_length=20, choices=SettlementStatus.choices, default=SettlementStatus.HOLD)

    class Meta:
        ordering = ["-created_at"]

    def save(self, *args, **kwargs):
        if not self.tracking_number:
            self.tracking_number = f"TRK-{timezone.now().strftime('%Y%m%d%H%M%S%f')}"
        if self.delivered_at and not self.return_window_ends_at:
            self.return_window_ends_at = self.delivered_at + timedelta(days=10)
        if self.return_window_ends_at and not self.seller_settlement_at:
            self.seller_settlement_at = self.return_window_ends_at
        super().save(*args, **kwargs)

    def __str__(self) -> str:
        return self.order_number


class OrderItem(BaseModel):
    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="order_items")
    product_name = models.CharField(max_length=220)
    sku = models.CharField(max_length=80)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)
    quantity = models.PositiveIntegerField()
    line_total = models.DecimalField(max_digits=12, decimal_places=2)
    warranty_until = models.DateField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.product_name} x {self.quantity}"


class Payment(BaseModel):
    class Provider(models.TextChoices):
        RAZORPAY = "razorpay", "Razorpay"
        STRIPE = "stripe", "Stripe"
        CASH_ON_DELIVERY = "cash_on_delivery", "Cash on delivery"

    class Status(models.TextChoices):
        INITIATED = "initiated", "Initiated"
        AUTHORIZED = "authorized", "Authorized"
        CAPTURED = "captured", "Captured"
        FAILED = "failed", "Failed"
        REFUNDED = "refunded", "Refunded"

    order = models.OneToOneField(Order, on_delete=models.CASCADE, related_name="payment")
    provider = models.CharField(max_length=40, choices=Provider.choices, default=Provider.RAZORPAY)
    transaction_id = models.CharField(max_length=120, blank=True)
    amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.INITIATED)
    paid_at = models.DateTimeField(null=True, blank=True)
    raw_payload = models.JSONField(default=dict, blank=True)

    def __str__(self) -> str:
        return f"{self.order.order_number} - {self.status}"


class OrderTrackingEvent(BaseModel):
    class EventType(models.TextChoices):
        PLACED = "placed", "Placed"
        CONFIRMED = "confirmed", "Confirmed"
        PACKED = "packed", "Packed"
        SHIPPED = "shipped", "Shipped"
        OUT_FOR_DELIVERY = "out_for_delivery", "Out for delivery"
        DELIVERED = "delivered", "Delivered"
        RETURN_REQUESTED = "return_requested", "Return requested"
        RETURNED = "returned", "Returned"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="tracking_events")
    event_type = models.CharField(max_length=30, choices=EventType.choices)
    title = models.CharField(max_length=120)
    description = models.TextField(blank=True)
    location = models.CharField(max_length=160, blank=True)
    occurred_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["occurred_at", "created_at"]

    def __str__(self) -> str:
        return f"{self.order.order_number} - {self.title}"


class ReturnRequest(BaseModel):
    class Status(models.TextChoices):
        REQUESTED = "requested", "Requested"
        APPROVED = "approved", "Approved"
        REJECTED = "rejected", "Rejected"
        PICKED_UP = "picked_up", "Picked up"
        COMPLETED = "completed", "Completed"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="return_requests")
    order_item = models.ForeignKey(OrderItem, on_delete=models.CASCADE, related_name="return_requests")
    reason = models.CharField(max_length=255)
    details = models.TextField(blank=True)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.REQUESTED)
    requested_at = models.DateTimeField(default=timezone.now)
    processed_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"Return request for {self.order.order_number}"


class NotificationLog(BaseModel):
    class Channel(models.TextChoices):
        EMAIL = "email", "Email"
        SMS = "sms", "SMS"
        WHATSAPP = "whatsapp", "WhatsApp"
        IN_APP = "in_app", "In app"

    class Status(models.TextChoices):
        QUEUED = "queued", "Queued"
        SENT = "sent", "Sent"
        FAILED = "failed", "Failed"

    order = models.ForeignKey(Order, on_delete=models.CASCADE, related_name="notifications")
    recipient = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.SET_NULL, null=True, blank=True, related_name="received_notifications")
    channel = models.CharField(max_length=20, choices=Channel.choices)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.QUEUED)
    subject = models.CharField(max_length=160, blank=True)
    message = models.TextField()
    provider_reference = models.CharField(max_length=120, blank=True)
    delivered_at = models.DateTimeField(null=True, blank=True)

    def __str__(self) -> str:
        return f"{self.order.order_number} - {self.channel}"
