from django.urls import include, path

from .views import account, cart, checkout, home, membership, offers, payment, product_detail, receipt, return_order_item, review_order_item, seller, seller_dashboard, shop, track_order

urlpatterns = [
    path("", home, name="home"),
    path("shop/", shop, name="shop"),
    path("offers/", offers, name="offers"),
    path("product/<slug:slug>/", product_detail, name="product-detail"),
    path("cart/", cart, name="cart"),
    path("cart/", include("apps.cart.urls")),
    path("checkout/", checkout, name="checkout"),
    path("membership/", membership, name="membership"),
    path("payment/<slug:order_number>/", payment, name="payment"),
    path("track-order/", track_order, name="track-order"),
    path("receipt/<slug:order_number>/", receipt, name="receipt"),
    path("orders/<slug:order_number>/items/<uuid:item_id>/review/", review_order_item, name="review-order-item"),
    path("orders/<slug:order_number>/items/<uuid:item_id>/return/", return_order_item, name="return-order-item"),
    path("seller-dashboard/", seller_dashboard, name="seller-dashboard"),
    path("account/", account, name="account"),
    path("sell/", seller, name="seller"),
]
