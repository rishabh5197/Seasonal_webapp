"""Root URL configuration."""

from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.website.views import not_found

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include("apps.website.urls")),
    path("auth/", include(("apps.accounts.urls", "site_auth"), namespace="site_auth")),
    path("api/schema/", SpectacularAPIView.as_view(), name="schema"),
    path("api/docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("api/", include("apps.core.urls")),
    path("api/auth/", include("apps.accounts.api_urls")),
    path("api/catalog/", include("apps.catalog.urls")),
    path("api/cart/", include("apps.cart.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/sellers/", include("apps.sellers.urls")),
]

handler404 = not_found
