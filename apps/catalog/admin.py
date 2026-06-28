from django.contrib import admin

from .models import Brand, Category, InventoryMovement, Product, ProductImage, ProductReview, ProductReviewImage


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "parent", "is_active", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Brand)
class BrandAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    search_fields = ("name", "slug")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ("name", "sku", "category", "owner", "base_price", "sale_price", "stock_quantity", "is_active")
    list_filter = ("is_active", "is_approved", "is_featured", "category", "brand")
    search_fields = ("name", "sku", "description", "owner__email")
    prepopulated_fields = {"slug": ("name",)}


@admin.register(ProductImage)
class ProductImageAdmin(admin.ModelAdmin):
    list_display = ("product", "sort_order", "is_primary")


@admin.register(InventoryMovement)
class InventoryMovementAdmin(admin.ModelAdmin):
    list_display = ("product", "movement_type", "quantity", "reference", "created_at")
    list_filter = ("movement_type",)
    search_fields = ("product__name", "reference", "note")


class ProductReviewImageInline(admin.TabularInline):
    model = ProductReviewImage
    extra = 0


@admin.register(ProductReview)
class ProductReviewAdmin(admin.ModelAdmin):
    list_display = ("product", "user", "rating", "is_verified_purchase", "is_approved", "created_at")
    list_filter = ("rating", "is_approved", "is_verified_purchase")
    search_fields = ("product__name", "user__email", "title", "comment")
    inlines = [ProductReviewImageInline]
