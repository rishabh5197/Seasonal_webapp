from dataclasses import dataclass
from datetime import timedelta
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required, user_passes_test
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse, reverse_lazy
from django.db.models import Avg, Count, Q, Sum
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.cart.services import cart_items, cart_summary, clear_cart, get_or_create_cart, sync_cart_session
from apps.accounts.services import activate_premium_membership, is_premium_member_active
from apps.catalog.models import Category, Product
from apps.accounts.models import User
from apps.orders.forms import CheckoutForm, PaymentConfirmForm, ProductReviewForm, ReturnRequestForm
from apps.orders.models import Order, OrderItem, Payment, ReturnRequest
from apps.orders.services import capture_payment, create_order_from_cart, refresh_order_settlement, submit_product_review, submit_return_request
from apps.website.models import CommercePolicy, HomepageBanner


@dataclass(frozen=True)
class PriceBand:
    label: str
    min_value: int | None
    max_value: int | None


def _product_queryset():
    return (
        Product.objects.filter(is_active=True, is_approved=True)
        .select_related("category", "brand", "owner")
        .prefetch_related("images", "reviews")
        .annotate(
            approved_reviews=Count("reviews", filter=Q(reviews__is_approved=True), distinct=True),
            average_rating=Avg("reviews__rating", filter=Q(reviews__is_approved=True)),
            sold_units=Sum("order_items__quantity"),
            sold_revenue=Sum("order_items__line_total"),
            effective_price=Coalesce("sale_price", "base_price"),
        )
    )


def _price_bands() -> list[PriceBand]:
    return [
        PriceBand("Under ₹999", None, 999),
        PriceBand("₹1k - ₹2.5k", 1000, 2500),
        PriceBand("₹2.5k - ₹5k", 2500, 5000),
        PriceBand("₹5k+", 5000, None),
    ]


def _apply_product_filters(request, queryset):
    search = request.GET.get("q", "").strip()
    category = request.GET.get("category", "").strip()
    brand = request.GET.get("brand", "").strip()
    min_price = request.GET.get("min_price", "").strip()
    max_price = request.GET.get("max_price", "").strip()
    sort = request.GET.get("sort", "featured").strip()
    only_in_stock = request.GET.get("in_stock") == "1"
    min_rating = request.GET.get("min_rating", "").strip()

    if search:
        queryset = queryset.filter(
            Q(name__icontains=search)
            | Q(description__icontains=search)
            | Q(category__name__icontains=search)
            | Q(brand__name__icontains=search)
        )
    if category:
        queryset = queryset.filter(category__slug=category)
    if brand:
        queryset = queryset.filter(brand__slug=brand)
    if min_price:
        queryset = queryset.filter(effective_price__gte=Decimal(min_price))
    if max_price:
        queryset = queryset.filter(effective_price__lte=Decimal(max_price))
    if only_in_stock:
        queryset = queryset.filter(stock_quantity__gt=0)
    if min_rating:
        queryset = queryset.filter(average_rating__gte=float(min_rating))

    if sort == "price_asc":
        queryset = queryset.order_by("effective_price", "-created_at")
    elif sort == "price_desc":
        queryset = queryset.order_by("-effective_price", "-created_at")
    elif sort == "rating":
        queryset = queryset.order_by("-average_rating", "-approved_reviews")
    elif sort == "newest":
        queryset = queryset.order_by("-created_at")
    elif sort == "popular":
        queryset = queryset.order_by("-sold_units", "-approved_reviews", "-created_at")
    else:
        queryset = queryset.order_by("-is_featured", "-approved_reviews", "-created_at")

    return queryset


def _warranty_until(order_item):
    if not order_item.warranty_until:
        months = getattr(order_item.product, "warranty_months", 0) or 0
        return (timezone.localdate() + timedelta(days=30 * months)) if months else None
    return order_item.warranty_until


def _order_item_rows(order):
    refresh_order_settlement(order)
    rows = []
    for item in order.items.select_related("product", "product__owner").prefetch_related("reviews__images", "return_requests"):
        review = item.reviews.filter(user=order.user).first()
        active_return = item.return_requests.order_by("-created_at").first()
        rows.append(
            {
                "item": item,
                "review": review,
                "return_request": active_return,
                "can_review": bool(order.delivered_at),
                "can_return": bool(order.delivered_at and order.return_window_ends_at and timezone.now() <= order.return_window_ends_at and not active_return),
                "warranty_until": _warranty_until(item),
            }
        )
    return rows


def home(request):
    products = _product_queryset()
    featured_products = products.filter(is_featured=True)[:8]
    if not featured_products:
        featured_products = products[:8]
    latest_products = products[:8]
    categories = Category.objects.filter(is_active=True).annotate(product_count=Count("products", filter=Q(products__is_active=True, products__is_approved=True))).order_by("name")
    return render(
        request,
        "website/home.html",
        {
            "featured_products": featured_products,
            "latest_products": latest_products,
            "sale_categories": categories[:6],
            "stats": {
                "products": products.count(),
                "categories": categories.count(),
                "orders": Order.objects.count(),
            },
        },
    )


def shop(request):
    products = _apply_product_filters(request, _product_queryset())
    categories = Category.objects.filter(is_active=True).order_by("name")
    available_brands = (
        products.filter(brand__isnull=False)
        .values_list("brand__slug", "brand__name")
        .distinct()
        .order_by("brand__name")
    )
    return render(
        request,
        "website/shop.html",
        {
            "products": products[:48],
            "categories": categories,
            "brands": available_brands,
            "bands": _price_bands(),
            "sort": request.GET.get("sort", "featured"),
            "active_filters": request.GET,
        },
    )


def product_detail(request, slug: str):
    product = get_object_or_404(
        _product_queryset(),
        slug=slug,
    )
    related_products = (
        _product_queryset()
        .filter(category=product.category)
        .exclude(pk=product.pk)[:8]
    )
    reviews = product.reviews.filter(is_approved=True).select_related("user").prefetch_related("images")
    return render(
        request,
        "website/product_detail.html",
        {
            "product": product,
            "related_products": related_products,
            "reviews": reviews,
            "average_rating": product.average_rating or 0,
            "review_count": product.approved_reviews or 0,
        },
    )


def cart(request):
    cart = sync_cart_session(request, get_or_create_cart(request))
    line_items = list(cart_items(cart))
    summary = cart_summary(cart, user=request.user)
    recommendations = _product_queryset()[:4]
    return render(
        request,
        "website/cart.html",
        {
            "cart": cart,
            "items": line_items,
            "summary": summary,
            "recommended_products": recommendations,
        },
    )


@login_required(login_url=reverse_lazy("site_auth:login"))
def checkout(request):
    cart = sync_cart_session(request, get_or_create_cart(request))
    line_items = list(cart_items(cart))
    if not line_items:
        messages.info(request, "Your cart is empty. Add at least one product before checkout.")
        return redirect("cart")

    recommendations = _product_queryset()[:4]
    form = CheckoutForm(request.POST or None, user=request.user)
    summary = cart_summary(cart, user=request.user)

    if request.method == "POST" and form.is_valid():
        shipping_address = form.cleaned_data["shipping_address"]
        billing_address = shipping_address if form.cleaned_data["billing_same_as_shipping"] else form.cleaned_data["billing_address"]
        order = create_order_from_cart(
            user=request.user,
            cart=cart,
            shipping_address=shipping_address,
            billing_address=billing_address,
            payment_provider=form.cleaned_data["payment_provider"],
            note=form.cleaned_data.get("note", ""),
        )
        request.session["pending_order_number"] = order.order_number
        request.session.modified = True
        return redirect("payment", order_number=order.order_number)

    return render(
        request,
        "website/checkout.html",
        {
            "items": line_items,
            "cart": cart,
            "summary": summary,
            "form": form,
            "recommended_products": recommendations,
            "addresses": request.user.addresses.all().order_by("-is_default", "-created_at"),
        },
    )


@login_required(login_url=reverse_lazy("site_auth:login"))
def payment(request, order_number: str):
    order = get_object_or_404(
        Order.objects.select_related("user", "shipping_address", "billing_address", "payment").prefetch_related("items__product__owner"),
        order_number__iexact=order_number,
        user=request.user,
    )
    payment = order.payment
    form = PaymentConfirmForm(request.POST or None, initial={"provider": payment.provider})
    gateway_label = payment.get_provider_display()

    if request.method == "POST" and form.is_valid():
        payment = capture_payment(
            order,
            transaction_id=form.cleaned_data.get("transaction_id", ""),
            gateway_reference=form.cleaned_data.get("gateway_reference", ""),
            payload={"provider": form.cleaned_data["provider"]},
        )
        cart = get_or_create_cart(request)
        clear_cart(cart)
        sync_cart_session(request, cart)
        messages.success(request, f"Payment captured for {order.order_number}.")
        return redirect("receipt", order_number=order.order_number)

    return render(
        request,
        "website/payment.html",
        {
            "order": order,
            "payment": payment,
            "form": form,
            "gateway_label": gateway_label,
        },
    )


def track_order(request):
    order_number = request.GET.get("order_number", "").strip()
    order = None
    if order_number:
        order = (
            Order.objects.select_related("user", "shipping_address")
            .prefetch_related("items__product__owner", "tracking_events")
            .filter(Q(order_number__iexact=order_number) | Q(tracking_number__iexact=order_number))
            .first()
        )
        if order:
            refresh_order_settlement(order)
    return render(
        request,
        "website/track_order.html",
        {
            "order_number": order_number,
            "order": order,
            "events": order.tracking_events.all() if order else [],
        },
    )


def receipt(request, order_number: str):
    order = get_object_or_404(
        Order.objects.select_related("user", "shipping_address", "billing_address", "payment")
        .prefetch_related("items__product__owner", "tracking_events"),
        Q(order_number__iexact=order_number) | Q(tracking_number__iexact=order_number),
    )
    refresh_order_settlement(order)
    payment = None
    try:
        payment = order.payment
    except Payment.DoesNotExist:
        payment = None
    return render(
        request,
        "website/receipt.html",
        {
            "order": order,
            "payment": payment,
            "receipt_items": _order_item_rows(order),
        },
    )


@login_required(login_url=reverse_lazy("site_auth:login"))
def review_order_item(request, order_number: str, item_id):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items__reviews", "items__return_requests"),
        order_number__iexact=order_number,
        user=request.user,
    )
    order_item = get_object_or_404(order.items.select_related("product"), pk=item_id)
    form = ProductReviewForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            submit_product_review(
                user=request.user,
                order_item=order_item,
                rating=int(form.cleaned_data["rating"]),
                title=form.cleaned_data.get("title", ""),
                comment=form.cleaned_data["comment"],
                photos=form.cleaned_data.get("photos") or [],
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Review saved for {order_item.product.name}.")
    elif request.method == "POST":
        messages.error(request, "Please complete the review form correctly.")
    return redirect("receipt", order_number=order.order_number)


@login_required(login_url=reverse_lazy("site_auth:login"))
def return_order_item(request, order_number: str, item_id):
    order = get_object_or_404(
        Order.objects.select_related("user").prefetch_related("items__reviews", "items__return_requests"),
        order_number__iexact=order_number,
        user=request.user,
    )
    order_item = get_object_or_404(order.items.select_related("product"), pk=item_id)
    form = ReturnRequestForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            submit_return_request(
                user=request.user,
                order_item=order_item,
                reason=form.cleaned_data["reason"],
                details=form.cleaned_data.get("details", ""),
            )
        except ValueError as exc:
            messages.error(request, str(exc))
        else:
            messages.success(request, f"Return request sent for {order_item.product.name}.")
    elif request.method == "POST":
        messages.error(request, "Please complete the return form correctly.")
    return redirect("receipt", order_number=order.order_number)


def _is_seller(user):
    return user.is_authenticated and (user.role == User.Role.SELLER or user.is_staff or user.role == User.Role.ADMIN)


@user_passes_test(_is_seller, login_url=reverse_lazy("site_auth:seller-login"))
def seller_dashboard(request):
    seller = getattr(request.user, "is_authenticated", False) and (
        getattr(request.user, "role", "") == "seller"
        or getattr(request.user, "role", "") == "admin"
        or getattr(request.user, "is_staff", False)
    )
    products = Product.objects.none()
    performance_rows = []
    category_rows = {}
    revenue_total = Decimal("0.00")
    settled_total = Decimal("0.00")
    held_total = Decimal("0.00")
    units_total = 0

    if seller:
        products = Product.objects.filter(owner=request.user).select_related("category").prefetch_related("reviews", "order_items__order")
        for product in products:
            revenue = Decimal("0.00")
            settled_revenue = Decimal("0.00")
            held_revenue = Decimal("0.00")
            sold_units = 0
            for item in product.order_items.all():
                refresh_order_settlement(item.order)
                revenue += item.line_total
                sold_units += item.quantity
                if item.order.settlement_status == Order.SettlementStatus.RELEASED:
                    settled_revenue += item.line_total
                else:
                    held_revenue += item.line_total
            average_rating = product.reviews.filter(is_approved=True).aggregate(avg=Avg("rating"))["avg"] or 0
            revenue_total += revenue
            settled_total += settled_revenue
            held_total += held_revenue
            units_total += sold_units
            category_key = product.category.name
            category_rows.setdefault(category_key, Decimal("0.00"))
            category_rows[category_key] += revenue
            performance_rows.append(
                {
                    "product": product,
                    "revenue": revenue,
                    "settled_revenue": settled_revenue,
                    "held_revenue": held_revenue,
                    "units": sold_units,
                    "average_rating": average_rating,
                    "review_count": product.reviews.filter(is_approved=True).count(),
                }
            )

    return render(
        request,
        "website/seller_dashboard.html",
        {
            "is_seller": seller,
            "products": performance_rows[:10],
            "category_rows": category_rows.items(),
            "revenue_total": revenue_total,
            "settled_total": settled_total,
            "held_total": held_total,
            "units_total": units_total,
            "product_count": products.count() if seller else 0,
        },
    )


@login_required(login_url=reverse_lazy("site_auth:login"))
def account(request):
    user = request.user
    premium_active = is_premium_member_active(user)
    return render(
        request,
        "website/account.html",
        {
            "profile": {
                "name": user.full_name,
                "email": user.email,
                "role": user.get_role_display(),
                "birth_date": user.birth_date,
                "gender": user.get_gender_display() if user.gender else "",
                "avatar_choice": user.avatar_choice,
                "avatar_image": user.avatar_image,
                "avatar_glyph": user.avatar_glyph,
            },
            "membership": {
                "is_active": premium_active,
                "expires_at": user.premium_membership_until,
                "annual_fee": CommercePolicy.current().premium_membership_annual_fee,
            },
            "stats": [
                {"label": "Orders placed", "value": user.orders.count()},
                {"label": "Addresses saved", "value": user.addresses.count()},
                {"label": "Role", "value": user.get_role_display()},
            ],
            "recent_orders": user.orders.prefetch_related("items").all()[:5],
        },
    )


@login_required(login_url=reverse_lazy("site_auth:login"))
def membership(request):
    policy = CommercePolicy.current()
    user = request.user
    premium_active = is_premium_member_active(user)

    if request.method == "POST":
        activate_premium_membership(user, policy=policy)
        messages.success(
            request,
            f"Premium membership activated. Your access now runs until {user.premium_membership_until:%d %b %Y}.",
        )
        return redirect("membership")

    return render(
        request,
        "website/membership.html",
        {
            "policy": policy,
            "premium_active": premium_active,
            "premium_expires_at": user.premium_membership_until,
            "benefits": [
                "High priority handling on customer support and order processing.",
                "Early access to new products and sale drops before non-premium shoppers.",
                "Early delivery benefits compared with non-premium membership.",
                "Lower shipping threshold with free shipping once your premium cart crosses the configured limit.",
            ],
            "comparison_rows": [
                {
                    "label": "Shipping threshold",
                    "premium": f"Free above Rs {policy.premium_free_shipping_threshold}",
                    "regular": f"Free above Rs {policy.non_premium_free_shipping_threshold}",
                },
                {
                    "label": "Order priority",
                    "premium": "High priority",
                    "regular": "Standard queue",
                },
                {
                    "label": "Access to sales",
                    "premium": "Early access",
                    "regular": "Standard access",
                },
                {
                    "label": "Delivery speed",
                    "premium": "Faster dispatch",
                    "regular": "Standard dispatch",
                },
            ],
        },
    )


@user_passes_test(_is_seller, login_url=reverse_lazy("site_auth:seller-login"))
def seller(request):
    return render(request, "website/seller.html")


def offers(request):
    live_banners = list(HomepageBanner.objects.filter(is_active=True).order_by("sort_order", "-created_at"))
    products = _product_queryset()
    sale_products = [
        product
        for product in products
        if product.sale_price is not None and product.sale_price < product.base_price
    ][:8]
    sale_categories = list(
        Category.objects.filter(is_active=True)
        .annotate(active_products=Count("products", filter=Q(products__is_active=True, products__is_approved=True)))
        .filter(active_products__gt=0)
        .order_by("-active_products", "name")[:6]
    )

    offers = []
    for banner in live_banners:
        date_label = "Live now"
        if banner.start_at and banner.end_at:
            date_label = f"{banner.start_at:%d %b} - {banner.end_at:%d %b %Y}"
        offers.append(
            {
                "title": banner.title,
                "subtitle": banner.subtitle or "Admin-managed promotion",
                "tone": banner.accent or "hero",
                "date_label": date_label,
            }
        )

    for product in sale_products:
        discount = 0
        if product.base_price:
            discount = round((1 - (product.current_price / product.base_price)) * 100)
        offers.append(
            {
                "title": product.name,
                "subtitle": f"{discount}% off with current price at Rs {product.current_price}",
                "tone": "sunset" if discount >= 20 else "violet",
                "date_label": f"Seller: {product.owner.full_name}",
            }
        )

    if not offers:
        offers = [
            {
                "title": "No live promotions yet",
                "subtitle": "Ask the admin to create homepage banners or mark products on sale.",
                "tone": "hero",
                "date_label": "Admin action required",
            }
        ]

    highlights = [
        {"title": "Active banners", "value": len(live_banners)},
        {"title": "Sale products", "value": len(sale_products)},
        {"title": "Sale categories", "value": len(sale_categories)},
    ]

    return render(
        request,
        "website/offers.html",
        {
            "offers": offers[:6],
            "highlights": highlights,
            "sale_categories": sale_categories,
            "sale_products": sale_products[:4],
        },
    )


def not_found(request, exception=None):  # noqa: ARG001
    return render(request, "website/404.html", status=404)
