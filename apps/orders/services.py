from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal
import logging
from uuid import uuid4

from django.conf import settings
from django.core.mail import send_mail
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.catalog.models import InventoryMovement
from apps.cart.services import cart_items, cart_summary, clear_cart
from apps.catalog.models import ProductReview, ProductReviewImage
from apps.orders.models import NotificationLog, Order, OrderItem, OrderTrackingEvent, Payment, ReturnRequest


logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class PaymentProvider:
    value: str
    label: str


PAYMENT_PROVIDERS = (
    PaymentProvider("razorpay", "Razorpay"),
    PaymentProvider("stripe", "Stripe"),
    PaymentProvider("cash_on_delivery", "Cash on delivery"),
)


def payment_provider_choices():
    return [(provider.value, provider.label) for provider in PAYMENT_PROVIDERS]


def generate_order_number() -> str:
    stamp = timezone.now().strftime("%Y%m%d%H%M%S")
    suffix = uuid4().hex[:6].upper()
    return f"ORD-{stamp}-{suffix}"


def calculate_checkout_summary(cart, user=None):
    return cart_summary(cart, user=user)


def _format_seller_items(order: Order, seller: User) -> str:
    seller_items = order.items.select_related("product", "product__owner").filter(product__owner=seller)
    return ", ".join(f"{item.product_name} x {item.quantity}" for item in seller_items)


@transaction.atomic
def notify_sellers_about_order(order: Order) -> None:
    seller_ids = (
        order.items.select_related("product", "product__owner")
        .values_list("product__owner_id", flat=True)
        .distinct()
    )
    sellers = User.objects.filter(id__in=seller_ids)

    subject = f"New order placed: {order.order_number}"
    default_from_email = getattr(settings, "DEFAULT_FROM_EMAIL", None)
    channels = getattr(settings, "SELLER_ORDER_ALERT_CHANNELS", ["email", "sms", "whatsapp"])

    for seller in sellers:
        item_summary = _format_seller_items(order, seller)
        message = (
            f"Hello {seller.full_name},\n\n"
            f"A new order has been placed on {getattr(settings, 'SITE_NAME', 'the store')}.\n"
            f"Order number: {order.order_number}\n"
            f"Customer: {order.user.full_name} ({order.user.email})\n"
            f"Items: {item_summary}\n"
            f"Order total: Rs {order.grand_total}\n"
        )
        if "email" in channels and seller.email:
            try:
                send_mail(subject, message, default_from_email, [seller.email], fail_silently=False)
            except Exception as exc:  # pragma: no cover - provider/network failure path
                logger.exception("Failed to send seller order email for %s", order.order_number)
                NotificationLog.objects.create(
                    order=order,
                    recipient=seller,
                    channel=NotificationLog.Channel.EMAIL,
                    status=NotificationLog.Status.FAILED,
                    subject=subject,
                    message=f"{message}\n\nDelivery error: {exc}",
                    provider_reference="email:error",
                )
            else:
                NotificationLog.objects.create(
                    order=order,
                    recipient=seller,
                    channel=NotificationLog.Channel.EMAIL,
                    status=NotificationLog.Status.SENT,
                    subject=subject,
                    message=message,
                    provider_reference="email:send_mail",
                    delivered_at=timezone.now(),
                )

        if "sms" in channels and seller.phone_number:
            NotificationLog.objects.create(
                order=order,
                recipient=seller,
                channel=NotificationLog.Channel.SMS,
                status=NotificationLog.Status.SENT,
                subject=subject,
                message=message,
                provider_reference="sms:local-stub",
                delivered_at=timezone.now(),
            )

        if "whatsapp" in channels and seller.phone_number:
            NotificationLog.objects.create(
                order=order,
                recipient=seller,
                channel=NotificationLog.Channel.WHATSAPP,
                status=NotificationLog.Status.SENT,
                subject=subject,
                message=message,
                provider_reference="whatsapp:local-stub",
                delivered_at=timezone.now(),
            )


@transaction.atomic
def create_order_from_cart(*, user, cart, shipping_address, billing_address=None, payment_provider: str, note: str = "") -> Order:
    items = list(cart_items(cart))
    if not items:
        raise ValueError("Cart is empty.")

    summary = cart_summary(cart, user=user)
    order = Order.objects.create(
        user=user,
        order_number=generate_order_number(),
        status=Order.Status.PENDING,
        shipping_address=shipping_address,
        billing_address=billing_address or shipping_address,
        subtotal=summary["subtotal"],
        shipping_fee=summary["shipping_fee"],
        tax_total=summary["tax_total"],
        discount_total=summary["discount_total"],
        grand_total=summary["grand_total"],
        notes=note or "",
        placed_at=timezone.now(),
    )

    for item in items:
        warranty_until = None
        if item.product.warranty_months:
            warranty_until = timezone.localdate() + timedelta(days=30 * item.product.warranty_months)
        OrderItem.objects.create(
            order=order,
            product=item.product,
            product_name=item.product.name,
            sku=item.product.sku,
            unit_price=item.unit_price,
            quantity=item.quantity,
            line_total=item.line_total,
            warranty_until=warranty_until,
        )
        InventoryMovement.objects.create(
            product=item.product,
            movement_type=InventoryMovement.MovementType.RESERVED,
            quantity=item.quantity,
            reference=order.order_number,
            note="Reserved during checkout.",
        )

    payment = Payment.objects.create(
        order=order,
        provider=payment_provider,
        amount=summary["grand_total"],
        status=Payment.Status.INITIATED,
    )
    OrderTrackingEvent.objects.create(
        order=order,
        event_type=OrderTrackingEvent.EventType.PLACED,
        title="Order placed",
        description=f"Order created using {payment.get_provider_display()}.",
    )
    transaction.on_commit(lambda order_id=order.id: notify_sellers_about_order(Order.objects.get(id=order_id)))
    if payment_provider == "cash_on_delivery":
        order.status = Order.Status.CONFIRMED
        order.confirmed_at = timezone.now()
        order.save(update_fields=["status", "confirmed_at", "updated_at"])
        OrderTrackingEvent.objects.create(
            order=order,
            event_type=OrderTrackingEvent.EventType.CONFIRMED,
            title="Order confirmed",
            description="Cash on delivery order confirmed.",
        )
    return order


@transaction.atomic
def capture_payment(order: Order, *, transaction_id: str = "", gateway_reference: str = "", payload: dict | None = None) -> Payment:
    payment = order.payment
    payment.status = Payment.Status.CAPTURED
    payment.transaction_id = transaction_id or gateway_reference or payment.transaction_id or f"PAY-{uuid4().hex[:10].upper()}"
    payment.raw_payload = payload or {}
    payment.paid_at = timezone.now()
    payment.save(update_fields=["status", "transaction_id", "raw_payload", "paid_at", "updated_at"])

    order.status = Order.Status.CONFIRMED
    if not order.confirmed_at:
        order.confirmed_at = timezone.now()
    order.save(update_fields=["status", "confirmed_at", "updated_at"])

    OrderTrackingEvent.objects.create(
        order=order,
        event_type=OrderTrackingEvent.EventType.CONFIRMED,
        title="Payment captured",
        description=f"Payment captured via {payment.get_provider_display()}.",
    )
    return payment


def release_cart_after_success(cart) -> None:
    clear_cart(cart)


@transaction.atomic
def refresh_order_settlement(order: Order) -> Order:
    now = timezone.now()
    changed_fields: list[str] = []

    if order.delivered_at:
        if not order.return_window_ends_at:
            order.return_window_ends_at = order.delivered_at + timedelta(days=10)
            changed_fields.append("return_window_ends_at")
        if not order.seller_settlement_at:
            order.seller_settlement_at = order.return_window_ends_at
            changed_fields.append("seller_settlement_at")

        active_return = order.return_requests.exclude(status=ReturnRequest.Status.REJECTED).exists()
        if active_return:
            target_status = Order.SettlementStatus.HOLD
        elif order.seller_settlement_at and now >= order.seller_settlement_at:
            target_status = Order.SettlementStatus.RELEASED
            if not order.seller_settled_at:
                order.seller_settled_at = now
                changed_fields.append("seller_settled_at")
        else:
            target_status = Order.SettlementStatus.ELIGIBLE
    else:
        target_status = Order.SettlementStatus.HOLD

    if order.settlement_status != target_status:
        order.settlement_status = target_status
        changed_fields.append("settlement_status")

    if changed_fields:
        order.save(update_fields=changed_fields + ["updated_at"])

    return order


@transaction.atomic
def submit_product_review(*, user, order_item: OrderItem, rating: int, title: str, comment: str, photos=None):
    order = order_item.order
    if order.user_id != user.id:
        raise ValueError("You can only review your own order.")
    if order.delivered_at is None:
        raise ValueError("Reviews are available after delivery.")

    review = order_item.reviews.filter(user=user).first()
    if review is None:
        review = ProductReview.objects.create(
            product=order_item.product,
            user=user,
            order_item=order_item,
            rating=rating,
            title=title,
            comment=comment,
            is_approved=True,
            is_verified_purchase=True,
        )
    else:
        review.rating = rating
        review.title = title
        review.comment = comment
        review.is_approved = True
        review.is_verified_purchase = True
        review.save(update_fields=["rating", "title", "comment", "is_approved", "is_verified_purchase", "updated_at"])
        review.images.all().delete()

    for photo in photos or []:
        ProductReviewImage.objects.create(review=review, image=photo)

    return review


@transaction.atomic
def submit_return_request(*, user, order_item: OrderItem, reason: str, details: str = "") -> ReturnRequest:
    order = order_item.order
    if order.user_id != user.id:
        raise ValueError("You can only return items from your own order.")
    if order.delivered_at is None:
        raise ValueError("Returns are available after delivery.")

    refresh_order_settlement(order)
    if order.return_window_ends_at and timezone.now() > order.return_window_ends_at:
        raise ValueError("The return window has closed.")

    existing_request = order.return_requests.filter(order_item=order_item).exclude(
        status__in=[ReturnRequest.Status.REJECTED, ReturnRequest.Status.COMPLETED]
    ).first()
    if existing_request:
        raise ValueError("A return request already exists for this item.")

    request = ReturnRequest.objects.create(
        order=order,
        order_item=order_item,
        reason=reason,
        details=details,
    )
    order.settlement_status = Order.SettlementStatus.HOLD
    order.save(update_fields=["settlement_status", "updated_at"])

    OrderTrackingEvent.objects.create(
        order=order,
        event_type=OrderTrackingEvent.EventType.RETURN_REQUESTED,
        title="Return requested",
        description=f"Return requested for {order_item.product_name}.",
    )
    return request
