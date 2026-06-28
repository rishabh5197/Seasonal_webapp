from django import forms

from .models import User


class RegisterForm(forms.Form):
    full_name = forms.CharField(max_length=150, widget=forms.TextInput(attrs={"placeholder": "Your full name"}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={"placeholder": "name@example.com"}))
    phone_number = forms.CharField(required=False, max_length=20, widget=forms.TextInput(attrs={"placeholder": "Phone number"}))
    birth_date = forms.DateField(
        required=False,
        input_formats=["%d-%m-%Y", "%d/%m/%Y", "%d %b %Y", "%d %B %Y", "%Y-%m-%d"],
        widget=forms.TextInput(
            attrs={
                "class": "date-picker__display",
                "placeholder": "DD-MM-YYYY",
                "autocomplete": "bday",
                "data-date-input": "true",
                "inputmode": "numeric",
            }
        ),
    )
    gender = forms.ChoiceField(
        required=False,
        choices=User.Gender.choices,
        widget=forms.RadioSelect,
    )
    avatar_choice = forms.ChoiceField(
        required=False,
        choices=[(value, glyph) for value, glyph in User.avatar_glyphs().items()],
        initial=User.Avatar.SMILE,
        widget=forms.Select(attrs={"class": "avatar-select"}),
    )
    avatar_image = forms.ImageField(
        required=False,
        widget=forms.ClearableFileInput(attrs={"accept": "image/*"}),
    )
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Create a password"}))
    password_confirm = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Confirm password"}))

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError("An account with this email already exists.")
        return email

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("password") != cleaned.get("password_confirm"):
            raise forms.ValidationError("Passwords do not match.")
        return cleaned


class LoginForm(forms.Form):
    identifier = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Email address or mobile number"}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={"placeholder": "Enter your password"}))


class OTPRequestForm(forms.Form):
    identifier = forms.CharField(widget=forms.TextInput(attrs={"placeholder": "Email address or mobile number"}))


class OTPVerifyForm(forms.Form):
    token = forms.UUIDField(widget=forms.HiddenInput())
    code = forms.CharField(
        min_length=4,
        max_length=10,
        widget=forms.TextInput(attrs={"placeholder": "Enter OTP code"}),
    )
