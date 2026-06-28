from decimal import Decimal

from django.db import models

from apps.core.models import BaseModel


class CommercePolicy(BaseModel):
    shipping_fee_amount = models.DecimalField(max_digits=12, decimal_places=2, default=49)
    premium_free_shipping_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=200)
    non_premium_free_shipping_threshold = models.DecimalField(max_digits=12, decimal_places=2, default=1000)
    premium_membership_annual_fee = models.DecimalField(max_digits=12, decimal_places=2, default=500)
    premium_membership_duration_days = models.PositiveIntegerField(default=365)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["-is_active", "-created_at"]

    @classmethod
    def current(cls) -> "CommercePolicy":
        policy = cls.objects.filter(is_active=True).order_by("-created_at").first()
        if policy:
            return policy
        return cls(
            shipping_fee_amount=Decimal("49.00"),
            premium_free_shipping_threshold=Decimal("200.00"),
            non_premium_free_shipping_threshold=Decimal("1000.00"),
            premium_membership_annual_fee=Decimal("500.00"),
            premium_membership_duration_days=365,
            is_active=True,
        )

    def __str__(self) -> str:
        return "Active commerce policy"


class HomepageBanner(BaseModel):
    title = models.CharField(max_length=180)
    subtitle = models.CharField(max_length=240, blank=True)
    badge = models.CharField(max_length=80, blank=True)
    cta_label = models.CharField(max_length=80, blank=True)
    cta_url = models.CharField(max_length=255, blank=True)
    desktop_image = models.ImageField(upload_to="homepage-banners/", blank=True, null=True)
    mobile_image = models.ImageField(upload_to="homepage-banners/mobile/", blank=True, null=True)
    start_at = models.DateTimeField(null=True, blank=True)
    end_at = models.DateTimeField(null=True, blank=True)
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)
    accent = models.CharField(max_length=32, default="violet")

    class Meta:
        ordering = ["sort_order", "-created_at"]

    def __str__(self) -> str:
        return self.title
