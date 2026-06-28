from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response


@api_view(["GET"])
@permission_classes([AllowAny])
def health_check(request):
    return Response(
        {
            "status": "ok",
            "service": "ecommerce-api",
            "timestamp": timezone.now().isoformat(),
        }
    )


@api_view(["GET"])
@permission_classes([AllowAny])
def api_root(request):
    return Response(
        {
            "health": "/api/health/",
            "auth": "/api/auth/",
            "catalog": "/api/catalog/",
            "cart": "/api/cart/",
            "orders": "/api/orders/",
            "sellers": "/api/sellers/",
            "schema": "/api/schema/",
            "docs": "/api/docs/",
        }
    )

