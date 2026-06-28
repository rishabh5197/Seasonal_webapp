app_name = "site_auth"

from django.urls import path

from .models import User
from .views import login_view, logout_view, otp_request_view, otp_verify_view
from .views import register_view


urlpatterns = [
    path("register/", register_view, name="register"),
    path("login/", login_view, kwargs={"role": User.Role.CUSTOMER}, name="login"),
    path("seller/login/", login_view, kwargs={"role": User.Role.SELLER}, name="seller-login"),
    path("admin/login/", login_view, kwargs={"role": User.Role.ADMIN}, name="admin-login"),
    path("otp/", otp_request_view, kwargs={"role": User.Role.CUSTOMER}, name="otp-login"),
    path("seller/otp/", otp_request_view, kwargs={"role": User.Role.SELLER}, name="seller-otp-login"),
    path("admin/otp/", otp_request_view, kwargs={"role": User.Role.ADMIN}, name="admin-otp-login"),
    path("otp/verify/<uuid:token>/", otp_verify_view, name="otp-verify"),
    path("logout/", logout_view, name="logout"),
]
