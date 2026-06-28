from datetime import timedelta
import re
from secrets import randbelow

from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.core.mail import send_mail
from django.utils import timezone

from .models import AuthOTP, User
from apps.website.models import CommercePolicy


OTP_EXPIRY_MINUTES = 10
OTP_LENGTH = 6
OTP_RESEND_COOLDOWN_SECONDS = 30


def normalize_role(role: str) -> str:
    return role if role in User.Role.values else User.Role.CUSTOMER


def normalize_login_identifier(identifier: str) -> str:
    return (identifier or "").strip()


def is_email_identifier(identifier: str) -> bool:
    cleaned_identifier = normalize_login_identifier(identifier)
    return "@" in cleaned_identifier or any(char.isalpha() for char in cleaned_identifier)


def normalize_phone_identifier(identifier: str) -> str:
    return re.sub(r"\D+", "", normalize_login_identifier(identifier))


def lookup_user_by_identifier(identifier: str) -> User:
    cleaned_identifier = normalize_login_identifier(identifier)
    if not cleaned_identifier:
        raise User.DoesNotExist

    if is_email_identifier(cleaned_identifier):
        return User.objects.get(email__iexact=cleaned_identifier)

    digits = normalize_phone_identifier(cleaned_identifier)
    if not digits:
        raise User.DoesNotExist

    for user in User.objects.exclude(phone_number="").only("id", "email", "phone_number", "role", "is_active", "is_staff", "full_name"):
        if normalize_phone_identifier(user.phone_number) == digits:
            return user
    raise User.DoesNotExist


def role_matches_user(user: User, role: str) -> bool:
    role = normalize_role(role)
    if role == User.Role.ADMIN:
        return user.is_staff or user.role == User.Role.ADMIN
    return user.role == role


def generate_otp() -> str:
    return f"{randbelow(10 ** OTP_LENGTH):0{OTP_LENGTH}d}"


def otp_resend_available_at(challenge: AuthOTP):
    return challenge.created_at + timedelta(seconds=OTP_RESEND_COOLDOWN_SECONDS)


def otp_resend_wait_seconds(challenge: AuthOTP) -> int:
    remaining = int((otp_resend_available_at(challenge) - timezone.now()).total_seconds())
    return max(0, remaining)


def create_otp_challenge(*, user: User, role: str, identifier: str = "") -> tuple[AuthOTP, str]:
    role = normalize_role(role)
    latest_challenge = (
        AuthOTP.objects.filter(user=user, role=role, purpose=AuthOTP.Purpose.LOGIN)
        .order_by("-created_at")
        .first()
    )
    if latest_challenge and otp_resend_wait_seconds(latest_challenge) > 0:
        raise ValueError(f"Please wait {otp_resend_wait_seconds(latest_challenge)} seconds before requesting a new OTP.")

    code = generate_otp()
    delivery_channel = "email" if is_email_identifier(identifier or user.email) else "sms"
    challenge = AuthOTP.objects.create(
        email=user.email,
        user=user,
        role=role,
        otp_hash=make_password(code),
        expires_at=timezone.now() + timedelta(minutes=OTP_EXPIRY_MINUTES),
        metadata={
            "identifier": normalize_login_identifier(identifier) or user.email,
            "delivery_channel": delivery_channel,
        },
    )
    send_mail(
        subject=f"Your {settings.SITE_NAME} login code",
        message=(
            f"Your one-time login code is {code}.\n\n"
            f"It expires in {OTP_EXPIRY_MINUTES} minutes.\n"
            f"If you did not request this, you can ignore this email."
        ),
        from_email=getattr(settings, "DEFAULT_FROM_EMAIL", None),
        recipient_list=[user.email],
        fail_silently=False,
    )
    return challenge, code


def resolve_user_by_login_identifier(identifier: str) -> User:
    user = lookup_user_by_identifier(identifier)
    if not user.is_active:
        raise ValueError("This account is inactive.")
    return user


def validate_otp_challenge(*, challenge: AuthOTP, code: str) -> User:
    if challenge.is_used:
        raise ValueError("This OTP has already been used.")
    if challenge.expires_at <= timezone.now():
        raise ValueError("This OTP has expired.")
    if challenge.attempts >= 5:
        raise ValueError("Too many incorrect attempts.")
    if not check_password(code, challenge.otp_hash):
        challenge.attempts += 1
        challenge.save(update_fields=["attempts", "updated_at"])
        raise ValueError("Invalid OTP.")

    challenge.is_used = True
    challenge.verified_at = timezone.now()
    challenge.save(update_fields=["is_used", "verified_at", "updated_at"])
    return challenge.user


def is_premium_member_active(user: User | None) -> bool:
    if not user or not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_premium_member", False):
        return False
    expires_at = getattr(user, "premium_membership_until", None)
    return expires_at is None or expires_at > timezone.now()


def activate_premium_membership(user: User, policy: CommercePolicy | None = None) -> User:
    policy = policy or CommercePolicy.current()
    now = timezone.now()
    current_until = getattr(user, "premium_membership_until", None)
    base_time = current_until if current_until and current_until > now else now
    user.is_premium_member = True
    user.premium_membership_until = base_time + timedelta(days=policy.premium_membership_duration_days)
    user.save(update_fields=["is_premium_member", "premium_membership_until", "updated_at"])
    return user
