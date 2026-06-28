from django.urls import path

from .views import add_to_cart, remove_item, update_item


urlpatterns = [
    path("add/<slug:slug>/", add_to_cart, name="add-to-cart"),
    path("item/<uuid:item_id>/update/", update_item, name="update-cart-item"),
    path("item/<uuid:item_id>/remove/", remove_item, name="remove-cart-item"),
]

