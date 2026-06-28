from django.contrib.auth import authenticate
from rest_framework import serializers

from .models import Address, AuthOTP, User
from .services import lookup_user_by_identifier, normalize_role, role_matches_user


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone_number",
            "birth_date",
            "gender",
            "avatar_choice",
            "avatar_image",
            "role",
            "is_email_verified",
            "date_joined",
        )
        read_only_fields = ("id", "role", "is_email_verified", "date_joined")


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True, min_length=8)

    class Meta:
        model = User
        fields = (
            "id",
            "email",
            "full_name",
            "phone_number",
            "birth_date",
            "gender",
            "avatar_choice",
            "avatar_image",
            "password",
            "password_confirm",
        )
        read_only_fields = ("id",)

    def validate(self, attrs):
        if attrs["password"] != attrs["password_confirm"]:
            raise serializers.ValidationError({"password_confirm": "Passwords do not match."})
        return attrs

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        password = validated_data.pop("password")
        validated_data.setdefault("birth_date", None)
        validated_data.setdefault("gender", "")
        validated_data.setdefault("avatar_choice", User.Avatar.SMILE)
        validated_data.setdefault("role", User.Role.CUSTOMER)
        user = User.objects.create_user(password=password, **validated_data)
        return user


class AddressSerializer(serializers.ModelSerializer):
    class Meta:
        model = Address
        fields = "__all__"
        read_only_fields = ("id", "user", "created_at", "updated_at")


class LoginSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    password = serializers.CharField(write_only=True, trim_whitespace=False)
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.CUSTOMER)

    def validate(self, attrs):
        role = normalize_role(attrs["role"])
        try:
            lookup_user_by_identifier(attrs["identifier"])
        except User.DoesNotExist as exc:
            raise serializers.ValidationError("Invalid email or mobile number.") from exc
        user = authenticate(
            request=self.context.get("request"),
            identifier=attrs["identifier"],
            password=attrs["password"],
        )
        if not user:
            raise serializers.ValidationError("Invalid email, mobile number, or password.")
        if not user.is_active:
            raise serializers.ValidationError("This account is inactive.")
        if not role_matches_user(user, role):
            raise serializers.ValidationError("This account does not have access to the selected role.")
        attrs["user"] = user
        attrs["role"] = role
        return attrs


class OTPRequestSerializer(serializers.Serializer):
    identifier = serializers.CharField()
    role = serializers.ChoiceField(choices=User.Role.choices, default=User.Role.CUSTOMER)

    def validate(self, attrs):
        role = normalize_role(attrs["role"])
        try:
            user = lookup_user_by_identifier(attrs["identifier"])
        except User.DoesNotExist as exc:
            raise serializers.ValidationError({"identifier": "No account found for this email or mobile number."}) from exc
        if not user.is_active:
            raise serializers.ValidationError({"identifier": "This account is inactive."})
        if not role_matches_user(user, role):
            raise serializers.ValidationError({"role": "This account cannot sign in with the selected role."})
        attrs["user"] = user
        attrs["role"] = role
        return attrs


class OTPVerifySerializer(serializers.Serializer):
    token = serializers.UUIDField()
    code = serializers.CharField(min_length=4, max_length=10, trim_whitespace=True)

    def validate(self, attrs):
        try:
            challenge = AuthOTP.objects.select_related("user").get(token=attrs["token"])
        except AuthOTP.DoesNotExist as exc:
            raise serializers.ValidationError({"token": "Invalid OTP token."}) from exc
        attrs["challenge"] = challenge
        return attrs
