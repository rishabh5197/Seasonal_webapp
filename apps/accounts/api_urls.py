from django.urls import include, path
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView

from .views import AddressViewSet, LoginAPIView, MeAPIView, OTPRequestAPIView, OTPVerifyAPIView, RegisterAPIView, LogoutAPIView


router = DefaultRouter()
router.register("addresses", AddressViewSet, basename="address")

urlpatterns = [
    path("register/", RegisterAPIView.as_view(), name="register"),
    path("me/", MeAPIView.as_view(), name="me"),
    path("login/", LoginAPIView.as_view(), name="login"),
    path("jwt/create/", LoginAPIView.as_view(), name="jwt-create"),
    path("jwt/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),
    path("logout/", LogoutAPIView.as_view(), name="logout"),
    path("otp/request/", OTPRequestAPIView.as_view(), name="otp-request"),
    path("otp/verify/", OTPVerifyAPIView.as_view(), name="otp-verify"),
    path("", include(router.urls)),
]
