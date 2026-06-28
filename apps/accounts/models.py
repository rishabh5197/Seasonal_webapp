from django.conf import settings
from django.contrib.auth.hashers import check_password, make_password
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models
from django.utils import timezone
from uuid import uuid4

from apps.core.models import BaseModel
from .managers import UserManager


class User(BaseModel, AbstractBaseUser, PermissionsMixin):
    class Avatar(models.TextChoices):
        FOX = "fox", "Fox"
        PANDA = "panda", "Panda"
        TIGER = "tiger", "Tiger"
        CAT = "cat", "Cat"
        DOG = "dog", "Dog"
        OWL = "owl", "Owl"
        LION = "lion", "Lion"
        BEAR = "bear", "Bear"
        RABBIT = "rabbit", "Rabbit"
        FROG = "frog", "Frog"
        KOALA = "koala", "Koala"
        PENGUIN = "penguin", "Penguin"
        UNICORN = "unicorn", "Unicorn"
        ROCKET = "rocket", "Rocket"
        STAR = "star", "Star"
        SUN = "sun", "Sun"
        MOON = "moon", "Moon"
        LEAF = "leaf", "Leaf"
        BOLT = "bolt", "Bolt"
        SMILE = "smile", "Smile"

    class Gender(models.TextChoices):
        MALE = "male", "Male"
        FEMALE = "female", "Female"
        OTHER = "other", "Other"

    class Role(models.TextChoices):
        CUSTOMER = "customer", "Customer"
        SELLER = "seller", "Seller"
        ADMIN = "admin", "Admin"

    email = models.EmailField(unique=True)
    full_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20, blank=True)
    birth_date = models.DateField(null=True, blank=True)
    gender = models.CharField(max_length=20, choices=Gender.choices, blank=True, default="")
    avatar_choice = models.CharField(max_length=20, choices=Avatar.choices, default=Avatar.SMILE)
    avatar_image = models.ImageField(upload_to="avatars/", blank=True, null=True)
    is_premium_member = models.BooleanField(default=False)
    premium_membership_until = models.DateTimeField(null=True, blank=True)
    role = models.CharField(max_length=20, choices=Role.choices, default=Role.CUSTOMER)
    is_email_verified = models.BooleanField(default=False)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    date_joined = models.DateTimeField(auto_now_add=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["full_name"]

    class Meta:
        ordering = ["full_name"]

    def __str__(self) -> str:
        return self.email

    @property
    def has_active_premium_membership(self) -> bool:
        if not self.is_premium_member:
            return False
        if self.premium_membership_until is None:
            return True
        return self.premium_membership_until > timezone.now()

    @property
    def avatar_glyph(self) -> str:
        return self.avatar_glyphs().get(self.avatar_choice, "☺")

    @classmethod
    def avatar_glyphs(cls) -> dict[str, str]:
        return {
            cls.Avatar.FOX: "🦊",
            cls.Avatar.PANDA: "🐼",
            cls.Avatar.TIGER: "🐯",
            cls.Avatar.CAT: "🐱",
            cls.Avatar.DOG: "🐶",
            cls.Avatar.OWL: "🦉",
            cls.Avatar.LION: "🦁",
            cls.Avatar.BEAR: "🐻",
            cls.Avatar.RABBIT: "🐰",
            cls.Avatar.FROG: "🐸",
            cls.Avatar.KOALA: "🐨",
            cls.Avatar.PENGUIN: "🐧",
            cls.Avatar.UNICORN: "🦄",
            cls.Avatar.ROCKET: "🚀",
            cls.Avatar.STAR: "⭐",
            cls.Avatar.SUN: "☀",
            cls.Avatar.MOON: "☾",
            cls.Avatar.LEAF: "🍃",
            cls.Avatar.BOLT: "⚡",
            cls.Avatar.SMILE: "☺",
        }

    @classmethod
    def avatar_options(cls) -> list[dict[str, str]]:
        glyphs = cls.avatar_glyphs()
        return [{"value": value, "label": label, "glyph": glyphs.get(value, "☺")} for value, label in cls.Avatar.choices]


class Address(BaseModel):
    class AddressType(models.TextChoices):
        HOME = "home", "Home"
        WORK = "work", "Work"
        OTHER = "other", "Other"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="addresses")
    label = models.CharField(max_length=80, default="Primary")
    address_type = models.CharField(max_length=20, choices=AddressType.choices, default=AddressType.HOME)
    recipient_name = models.CharField(max_length=150)
    phone_number = models.CharField(max_length=20)
    line_1 = models.CharField(max_length=255)
    line_2 = models.CharField(max_length=255, blank=True)
    landmark = models.CharField(max_length=120, blank=True)
    city = models.CharField(max_length=120)
    state = models.CharField(max_length=120)
    postal_code = models.CharField(max_length=20)
    country = models.CharField(max_length=120, default="India")
    is_default = models.BooleanField(default=False)

    class Meta:
        ordering = ["-is_default", "-created_at"]

    def __str__(self) -> str:
        return f"{self.label} - {self.city}"


class AuthOTP(BaseModel):
    class Purpose(models.TextChoices):
        LOGIN = "login", "Login"

    token = models.UUIDField(default=uuid4, unique=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="otp_challenges")
    email = models.EmailField()
    role = models.CharField(max_length=20, choices=User.Role.choices, default=User.Role.CUSTOMER)
    purpose = models.CharField(max_length=20, choices=Purpose.choices, default=Purpose.LOGIN)
    otp_hash = models.CharField(max_length=128)
    attempts = models.PositiveSmallIntegerField(default=0)
    expires_at = models.DateTimeField()
    verified_at = models.DateTimeField(null=True, blank=True)
    is_used = models.BooleanField(default=False)
    metadata = models.JSONField(default=dict, blank=True)

    class Meta:
        ordering = ["-created_at"]

    def set_code(self, code: str) -> None:
        self.otp_hash = make_password(code)

    def check_code(self, code: str) -> bool:
        return check_password(code, self.otp_hash)

    @property
    def is_expired(self) -> bool:
        return self.expires_at <= timezone.now()

    def __str__(self) -> str:
        return f"OTP {self.token}"
