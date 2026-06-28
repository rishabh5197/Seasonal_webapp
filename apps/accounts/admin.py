from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin

from .models import Address, User


@admin.register(User)
class UserAdmin(DjangoUserAdmin):
    model = User
    ordering = ("email",)
    list_display = ("email", "full_name", "role", "birth_date", "gender", "avatar_choice", "is_premium_member", "premium_membership_until", "is_staff", "is_active")
    list_filter = ("role", "gender", "avatar_choice", "is_premium_member", "is_staff", "is_active", "is_email_verified")
    search_fields = ("email", "full_name", "phone_number")
    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Profile", {"fields": ("full_name", "phone_number", "birth_date", "gender", "avatar_choice", "avatar_image", "is_premium_member", "premium_membership_until", "role", "is_email_verified")}),
        ("Permissions", {"fields": ("is_active", "is_staff", "is_superuser", "groups", "user_permissions")}),
        ("Dates", {"fields": ("last_login", "date_joined")}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": ("email", "full_name", "password1", "password2", "birth_date", "gender", "avatar_choice", "avatar_image", "role", "is_premium_member", "premium_membership_until", "is_staff", "is_active"),
            },
        ),
    )
    readonly_fields = ("date_joined",)


@admin.register(Address)
class AddressAdmin(admin.ModelAdmin):
    list_display = ("label", "user", "city", "state", "is_default", "created_at")
    search_fields = ("label", "recipient_name", "city", "state", "postal_code", "user__email")
    list_filter = ("address_type", "is_default", "country")
