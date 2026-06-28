from django.conf import settings
from django.db import models

from apps.catalog.models import Product
from apps.core.models import BaseModel


class Cart(BaseModel):
    user = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.CASCADE, related_name="cart")
    session_key = models.CharField(max_length=64, null=True, blank=True, unique=True)
    currency = models.CharField(max_length=12, default="INR")
    is_active = models.BooleanField(default=True)

    def __str__(self) -> str:
        return f"Cart {self.id}"

    @property
    def total_quantity(self):
        return sum(item.quantity for item in self.items.all())

    @property
    def subtotal(self):
        return sum(item.line_total for item in self.items.all())


class CartItem(BaseModel):
    cart = models.ForeignKey(Cart, on_delete=models.CASCADE, related_name="items")
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="cart_items")
    quantity = models.PositiveIntegerField(default=1)
    unit_price = models.DecimalField(max_digits=12, decimal_places=2)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["cart", "product"], name="unique_cart_product")
        ]

    @property
    def line_total(self):
        return self.quantity * self.unit_price

    def __str__(self) -> str:
        return f"{self.product.name} x {self.quantity}"
