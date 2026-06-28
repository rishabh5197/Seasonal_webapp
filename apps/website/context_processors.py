from django.conf import settings

from apps.catalog.models import Category
from .models import CommercePolicy, HomepageBanner


def storefront_globals(request):
    return {
        "site_name": settings.SITE_NAME,
        "site_tagline": settings.SITE_TAGLINE,
        "site_categories": Category.objects.filter(is_active=True).order_by("name"),
        "site_banners": HomepageBanner.objects.filter(is_active=True).order_by("sort_order", "-created_at"),
        "commerce_policy": CommercePolicy.current(),
        "cart_count": request.session.get("cart_count", 0),
    }
