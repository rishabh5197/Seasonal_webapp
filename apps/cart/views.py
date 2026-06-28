from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect

from apps.catalog.models import Product

from .models import CartItem
from .services import add_product_to_cart, get_or_create_cart, remove_cart_item, sync_cart_session, update_cart_item


def _cart_access_allowed(request, cart) -> bool:
    if getattr(request.user, "is_authenticated", False):
        return cart.user_id == request.user.id
    return cart.session_key == request.session.session_key


def add_to_cart(request, slug: str):
    if request.method != "POST":
        return redirect("product-detail", slug=slug)

    product = get_object_or_404(Product.objects.select_related("category"), slug=slug, is_active=True, is_approved=True)
    quantity = request.POST.get("quantity", "1")
    cart = get_or_create_cart(request)
    try:
        add_product_to_cart(cart, product, quantity)
        sync_cart_session(request, cart)
        messages.success(request, f"{product.name} added to cart.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect(request.POST.get("next") or "cart")


def update_item(request, item_id):
    if request.method != "POST":
        return redirect("cart")

    cart_item = get_object_or_404(CartItem.objects.select_related("cart", "product"), pk=item_id)
    if not _cart_access_allowed(request, cart_item.cart):
        return redirect("cart")

    quantity = request.POST.get("quantity", "1")
    try:
        update_cart_item(cart_item, quantity)
        sync_cart_session(request, cart_item.cart)
        messages.success(request, f"Updated {cart_item.product.name}.")
    except ValueError as exc:
        messages.error(request, str(exc))
    return redirect("cart")


def remove_item(request, item_id):
    if request.method != "POST":
        return redirect("cart")

    cart_item = get_object_or_404(CartItem.objects.select_related("cart", "product"), pk=item_id)
    if not _cart_access_allowed(request, cart_item.cart):
        return redirect("cart")

    product_name = cart_item.product.name
    cart = cart_item.cart
    remove_cart_item(cart_item)
    sync_cart_session(request, cart)
    messages.info(request, f"Removed {product_name} from cart.")
    return redirect("cart")
