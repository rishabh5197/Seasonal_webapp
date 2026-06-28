from django import forms

from apps.accounts.models import Address


class MultipleFileInput(forms.ClearableFileInput):
    allow_multiple_selected = True


class MultipleImageField(forms.FileField):
    widget = MultipleFileInput

    def clean(self, data, initial=None):
        if not data:
            return []
        if isinstance(data, (list, tuple)):
            return [forms.FileField.clean(self, item, initial) for item in data if item]
        return [forms.FileField.clean(self, data, initial)]


class CheckoutForm(forms.Form):
    shipping_address = forms.ModelChoiceField(queryset=Address.objects.none())
    billing_same_as_shipping = forms.BooleanField(required=False, initial=True)
    billing_address = forms.ModelChoiceField(queryset=Address.objects.none(), required=False)
    payment_provider = forms.ChoiceField(
        choices=(
            ("razorpay", "Razorpay"),
            ("stripe", "Stripe"),
            ("cash_on_delivery", "Cash on delivery"),
        )
    )
    note = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 3}))

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        addresses = Address.objects.none()
        if user and user.is_authenticated:
            addresses = user.addresses.all().order_by("-is_default", "-created_at")
        self.fields["shipping_address"].queryset = addresses
        self.fields["billing_address"].queryset = addresses

    def clean(self):
        cleaned = super().clean()
        shipping = cleaned.get("shipping_address")
        billing_same = cleaned.get("billing_same_as_shipping")
        billing = cleaned.get("billing_address")
        if shipping is None:
            raise forms.ValidationError("Please add a shipping address before checkout.")
        if not billing_same and billing is None:
            raise forms.ValidationError("Please choose a billing address or enable same as shipping.")
        return cleaned


class PaymentConfirmForm(forms.Form):
    provider = forms.ChoiceField(
        choices=(
            ("razorpay", "Razorpay"),
            ("stripe", "Stripe"),
            ("cash_on_delivery", "Cash on delivery"),
        )
    )
    transaction_id = forms.CharField(required=False, max_length=120)
    gateway_reference = forms.CharField(required=False, max_length=120)


class ProductReviewForm(forms.Form):
    rating = forms.ChoiceField(choices=[(str(value), str(value)) for value in range(1, 6)])
    title = forms.CharField(required=False, max_length=120)
    comment = forms.CharField(widget=forms.Textarea(attrs={"rows": 4}))
    photos = MultipleImageField(required=False, widget=MultipleFileInput(attrs={"multiple": True, "accept": "image/*"}))


class ReturnRequestForm(forms.Form):
    reason = forms.CharField(max_length=255)
    details = forms.CharField(required=False, widget=forms.Textarea(attrs={"rows": 4}))
