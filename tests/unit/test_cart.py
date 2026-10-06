"""S152-08 — the ShoppingCart island, the twin of ``Cart.vue``.

The page cannot know the browser's ``vbwd_shop_cart``: the island posts it
(``data-vbwd-cart``) and this fragment renders the lines from the posted cart
(the SPA renders from the same stored lines), in the operating currency from
``GET /api/v1/config`` when a line carries none. Net/gross per line fall back
to the bare price; the footer subtotal is the gross sum (no display modes).
"""
import json

from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest
from plugins.theme_shop.theme_shop.cart import ShoppingCart

LINE = {
    "productId": "p-1",
    "productSlug": "mug",
    "productName": "Mug",
    "imageUrl": "/m.png",
    "price": 12.5,
    "quantity": 2,
    "maxQuantity": 2,
    "isDigital": False,
    "weight": 0.4,
    "netAmount": 10.5,
    "grossAmount": 12.5,
    "effectiveDisplayMode": "netto",
    "pricesDisplayMode": "brutto",
}
BARE_LINE = {
    "productId": "p-2",
    "productSlug": "cable",
    "productName": "Cable",
    "imageUrl": "",
    "price": 5,
    "quantity": 1,
    "maxQuantity": 9,
    "variantId": "v-9",
    "variantName": "2m",
}


def _cart(lines):
    api = FakeCheckoutApi(default_currency="USD")
    return ShoppingCart(api.factory).fragment_context(
        FakeThemeRequest({"cart": json.dumps(lines)})
    )


def test_an_empty_or_unreadable_cart_is_the_empty_state():
    assert _cart([])["state"] == "empty"
    assert (
        ShoppingCart(FakeCheckoutApi().factory).fragment_context(
            FakeThemeRequest({"cart": "{broken"})
        )["state"]
        == "empty"
    )


def test_each_line_carries_its_prices_quantity_limits_and_identity():
    context = _cart([LINE, BARE_LINE])

    first, second = context["lines"]
    assert first["unit_price"].label == "$10.50" and first["unit_price"].show_netto_tag
    assert first["subtotal"].label == "$21.00"
    assert first["can_decrease"] is True and first["can_increase"] is False
    assert first["product_id"] == "p-1" and first["variant_id"] == ""
    assert second["unit_price"].label == "$5.00"
    assert second["can_decrease"] is False and second["can_increase"] is True
    assert second["variant_id"] == "v-9" and second["variant_name"] == "2m"


def test_the_footer_counts_items_and_sums_the_gross():
    context = _cart([LINE, BARE_LINE])

    assert context["item_count"] == 3
    assert context["subtotal"].label == "$30.00"


def test_a_line_currency_wins_over_the_operating_currency():
    context = _cart([{**BARE_LINE, "currency": "EUR"}])

    assert context["lines"][0]["unit_price"].label == "€5.00"
