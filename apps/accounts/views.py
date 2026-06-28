from django.contrib import messages
from django.contrib.messages import get_messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.conf import settings
from django.db import IntegrityError
from django.shortcuts import redirect, render
from django.urls import reverse
from rest_framework import permissions, status, viewsets
from rest_framework.generics import CreateAPIView, RetrieveUpdateAPIView
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from .forms import LoginForm, OTPRequestForm, OTPVerifyForm, RegisterForm
from .models import Address, AuthOTP, User
from .serializers import (
    AddressSerializer,
    LoginSerializer,
    OTPRequestSerializer,
    OTPVerifySerializer,
    RegisterSerializer,
    UserSerializer,
)
from .services import (
    create_otp_challenge,
    normalize_role,
    otp_resend_available_at,
    otp_resend_wait_seconds,
    role_matches_user,
    resolve_user_by_login_identifier,
    validate_otp_challenge,
)


def _login_redirect_for(user: User, role: str) -> str:
    role = normalize_role(role)
    if role == User.Role.ADMIN or user.is_staff or user.role == User.Role.ADMIN:
        return reverse("admin:index")
    if role == User.Role.SELLER or user.role == User.Role.SELLER:
        return reverse("seller-dashboard")
    return reverse("account")


def _jwt_payload(user: User, role: str) -> dict:
    refresh = RefreshToken.for_user(user)
    return {
        "user": UserSerializer(user).data,
        "access": str(refresh.access_token),
        "refresh": str(refresh),
        "role": normalize_role(role),
    }


class RegisterAPIView(CreateAPIView):
    serializer_class = RegisterSerializer
    permission_classes = [permissions.AllowAny]

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        headers = self.get_success_headers(serializer.data)
        return Response(UserSerializer(user).data, status=201, headers=headers)


class MeAPIView(RetrieveUpdateAPIView):
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_object(self):
        return self.request.user


class AddressViewSet(viewsets.ModelViewSet):
    serializer_class = AddressSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        return Address.objects.filter(user=self.request.user)

    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class LoginAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        role = serializer.validated_data["role"]
        payload = _jwt_payload(user, role)
        return Response(payload)


class LogoutAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        refresh = request.data.get("refresh")
        if refresh:
            try:
                token = RefreshToken(refresh)
                token.blacklist()
            except Exception:
                return Response({"detail": "Invalid refresh token."}, status=status.HTTP_400_BAD_REQUEST)
        return Response({"detail": "Logged out successfully."}, status=status.HTTP_200_OK)


class OTPRequestAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data["user"]
        role = serializer.validated_data["role"]
        challenge, _code = create_otp_challenge(user=user, role=role, identifier=serializer.validated_data["identifier"])
        return Response(
            {
                "token": str(challenge.token),
                "expires_at": challenge.expires_at,
                "role": role,
                "detail": "OTP sent to the registered contact channel.",
            },
            status=status.HTTP_201_CREATED,
        )


class OTPVerifyAPIView(APIView):
    permission_classes = [permissions.AllowAny]

    def post(self, request):
        serializer = OTPVerifySerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        challenge = serializer.validated_data["challenge"]
        try:
            user = validate_otp_challenge(challenge=challenge, code=serializer.validated_data["code"])
        except ValueError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)
        if not role_matches_user(user, challenge.role):
            return Response(
                {"detail": "This account does not match the selected role."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        payload = _jwt_payload(user, challenge.role)
        return Response(payload, status=status.HTTP_200_OK)


def login_view(request, role=User.Role.CUSTOMER, mode="password"):
    role = normalize_role(role)
    if request.user.is_authenticated:
        return redirect(_login_redirect_for(request.user, role))

    active_mode = request.GET.get("mode", mode)
    if active_mode not in {"password", "otp"}:
        active_mode = "password"
    initial_identifier = request.session.get("pending_otp_identifier", "")
    password_form = LoginForm(prefix="password", initial={"identifier": initial_identifier})
    otp_form = OTPRequestForm(prefix="otp", initial={"identifier": initial_identifier})
    if request.method == "POST":
        action = request.POST.get("auth_action", active_mode)
        if action == "otp":
            active_mode = "otp"
            otp_form = OTPRequestForm(request.POST, prefix="otp")
            if otp_form.is_valid():
                identifier = otp_form.cleaned_data["identifier"]
                try:
                    user = resolve_user_by_login_identifier(identifier)
                    if not role_matches_user(user, role):
                        otp_form.add_error(None, "This account cannot sign in with that role.")
                    else:
                        challenge, _code = create_otp_challenge(user=user, role=role, identifier=identifier)
                        request.session["pending_otp_identifier"] = identifier
                        request.session["pending_otp_role"] = role
                        request.session.modified = True
                        messages.success(request, "OTP sent. Check your email or mobile number.")
                        return redirect("site_auth:otp-verify", token=challenge.token)
                except User.DoesNotExist:
                    otp_form.add_error("identifier", "No account found for this email or mobile number.")
                except ValueError as exc:
                    otp_form.add_error(None, str(exc))
        else:
            active_mode = "password"
            password_form = LoginForm(request.POST, prefix="password")
            if password_form.is_valid():
                identifier = password_form.cleaned_data["identifier"]
                password = password_form.cleaned_data["password"]
                from django.contrib.auth import authenticate

                user = authenticate(request, identifier=identifier, password=password)
                if not user:
                    password_form.add_error(None, "Invalid email, mobile number, or password.")
                elif not role_matches_user(user, role):
                    password_form.add_error(None, "This account cannot sign in with that role.")
                else:
                    auth_login(request, user)
                    messages.success(request, f"Welcome back, {user.full_name}.")
                    return redirect(_login_redirect_for(user, role))

    return render(
        request,
        "accounts/login.html",
        {
            "password_form": password_form,
            "otp_form": otp_form,
            "role": role,
            "active_mode": active_mode,
            "initial_identifier": initial_identifier,
        },
    )


def otp_request_view(request, role=User.Role.CUSTOMER):
    return login_view(request, role=role, mode="otp")


def register_view(request):
    if request.user.is_authenticated:
        return redirect("account")

    form = RegisterForm(request.POST or None, request.FILES or None)
    if request.method == "POST" and form.is_valid():
        try:
            user = User.objects.create_user(
                email=form.cleaned_data["email"],
                full_name=form.cleaned_data["full_name"],
                phone_number=form.cleaned_data.get("phone_number", ""),
                birth_date=form.cleaned_data.get("birth_date"),
                gender=form.cleaned_data.get("gender", ""),
                avatar_choice=form.cleaned_data.get("avatar_choice") or User.Avatar.SMILE,
                avatar_image=form.cleaned_data.get("avatar_image"),
                role=User.Role.CUSTOMER,
                password=form.cleaned_data["password"],
            )
        except IntegrityError:
            form.add_error("email", "An account with this email already exists.")
        else:
            auth_login(request, user, backend=settings.AUTHENTICATION_BACKENDS[0])
            messages.success(request, "Your account has been created.")
            return redirect("account")

    return render(
        request,
        "accounts/register.html",
        {
            "form": form,
        },
    )


def otp_verify_view(request, token):
    challenge = AuthOTP.objects.select_related("user").filter(token=token).first()
    if challenge is None:
        messages.error(request, "Invalid or expired OTP token.")
        return redirect("site_auth:otp-login")

    form = OTPVerifyForm(request.POST or None, initial={"token": challenge.token})
    if request.method == "POST" and form.is_valid():
        try:
            user = validate_otp_challenge(challenge=challenge, code=form.cleaned_data["code"])
        except ValueError as exc:
            form.add_error("code", str(exc))
        else:
            auth_login(request, user)
            messages.success(request, f"Logged in as {user.full_name} using OTP.")
            return redirect(_login_redirect_for(user, challenge.role))

    return render(
        request,
        "accounts/otp_verify.html",
        {
            "form": form,
            "challenge": challenge,
            "role": challenge.role,
            "resend_wait_seconds": otp_resend_wait_seconds(challenge),
            "resend_available_at": otp_resend_available_at(challenge),
            "pending_identifier": (challenge.metadata or {}).get("identifier", challenge.email),
        },
    )


def logout_view(request):
    if request.method in {"POST", "GET"}:
        auth_logout(request)
        list(get_messages(request))
        messages.info(request, "You have been logged out.")
    return redirect("home")
