from decimal import Decimal

from apps.catalog.models import InventoryMovement, Product
from apps.accounts.services import is_premium_member_active
from apps.website.models import CommercePolicy
from .models import Cart, CartItem


def _session_key(request) -> str:
    if not request.session.session_key:
        request.session.save()
    return request.session.session_key


def get_or_create_cart(request) -> Cart:
    user = getattr(request, "user", None)
    session_key = _session_key(request)

    if user and user.is_authenticated:
        guest_cart = Cart.objects.filter(session_key=session_key, user__isnull=True).first()
        if guest_cart:
            user_cart, _ = Cart.objects.get_or_create(user=user, defaults={"session_key": session_key})
            for item in guest_cart.items.select_related("product"):
                add_product_to_cart(user_cart, item.product, item.quantity)
            guest_cart.delete()
            return user_cart

        cart, _ = Cart.objects.get_or_create(user=user, defaults={"session_key": session_key})
        if cart.session_key != session_key:
            cart.session_key = session_key
            cart.save(update_fields=["session_key", "updated_at"])
        return cart

    cart = Cart.objects.filter(session_key=session_key, is_active=True, user__isnull=True).first()
    if cart:
        return cart
    return Cart.objects.create(session_key=session_key, is_active=True)


def cart_items(cart: Cart):
    return (
        cart.items.select_related("product", "product__category", "product__brand", "product__owner")
        .prefetch_related("product__images")
        .order_by("-created_at")
    )


def cart_count(cart: Cart) -> int:
    return sum(item.quantity for item in cart_items(cart))


def sync_cart_session(request, cart: Cart | None = None) -> Cart:
    cart = cart or get_or_create_cart(request)
    request.session["cart_count"] = cart_count(cart)
    request.session.modified = True
    return cart


def add_product_to_cart(cart: Cart, product: Product, quantity: int = 1) -> CartItem:
    quantity = max(1, int(quantity))
    existing = cart.items.filter(product=product).first()
    max_allowed = product.max_purchase_qty or product.stock_quantity or quantity
    target_quantity = min((existing.quantity if existing else 0) + quantity, product.stock_quantity or quantity, max_allowed)
    if target_quantity <= 0:
        raise ValueError("This product is out of stock.")

    unit_price = product.current_price
    if existing:
        existing.quantity = target_quantity
        existing.unit_price = unit_price
        existing.save(update_fields=["quantity", "unit_price", "updated_at"])
        return existing

    return cart.items.create(product=product, quantity=target_quantity, unit_price=unit_price)


def update_cart_item(item: CartItem, quantity: int) -> CartItem:
    quantity = max(1, int(quantity))
    max_allowed = item.product.max_purchase_qty or item.product.stock_quantity or quantity
    item.quantity = min(quantity, item.product.stock_quantity or quantity, max_allowed)
    item.unit_price = item.product.current_price
    item.save(update_fields=["quantity", "unit_price", "updated_at"])
    return item


def remove_cart_item(item: CartItem) -> None:
    item.delete()


def clear_cart(cart: Cart) -> None:
    cart.items.all().delete()


def cart_summary(cart: Cart, user=None) -> dict:
    subtotal = Decimal("0.00")
    list_total = Decimal("0.00")
    for item in cart_items(cart):
        subtotal += item.line_total
        list_total += item.product.base_price * item.quantity

    discount_total = max(list_total - subtotal, Decimal("0.00"))
    policy = CommercePolicy.current()
    is_premium_member = is_premium_member_active(user)
    shipping_fee_amount = policy.shipping_fee_amount
    premium_free_shipping_threshold = policy.premium_free_shipping_threshold
    non_premium_free_shipping_threshold = policy.non_premium_free_shipping_threshold
    shipping_threshold = premium_free_shipping_threshold if is_premium_member else non_premium_free_shipping_threshold

    shipping_fee = Decimal("0.00")
    if subtotal > Decimal("0.00") and subtotal < shipping_threshold:
        shipping_fee = shipping_fee_amount

    tax_total = (subtotal * Decimal("0.18")).quantize(Decimal("0.01"))
    grand_total = subtotal + shipping_fee + tax_total
    return {
        "subtotal": subtotal,
        "list_total": list_total,
        "discount_total": discount_total,
        "shipping_fee": shipping_fee,
        "tax_total": tax_total,
        "grand_total": grand_total,
        "is_premium_member": is_premium_member,
        "shipping_fee_amount": shipping_fee_amount,
        "premium_free_shipping_threshold": premium_free_shipping_threshold,
        "non_premium_free_shipping_threshold": non_premium_free_shipping_threshold,
        "shipping_threshold": shipping_threshold,
        "shipping_is_free": subtotal >= shipping_threshold and subtotal > Decimal("0.00"),
        "premium_membership_annual_fee": policy.premium_membership_annual_fee,
        "premium_membership_duration_days": policy.premium_membership_duration_days,
    }
