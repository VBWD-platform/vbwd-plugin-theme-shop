"""S152-08 — the "shop" checkout source, the twin of ``shop/checkoutSource.ts``.

``?source=shop`` checks out the shop cart (``vbwd_shop_cart``, posted by the
island): lines ``price × quantity``, coupon scope ``ECOMMERCE`` on the cart
subtotal, submit ``POST /api/v1/shop/cart/checkout`` with the items, payment
method and applied coupon; the answer becomes the PENDING invoice the dispatch
table routes. An empty cart is the SPA's "Cart is empty".
"""
from decimal import Decimal

import pytest

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_sources import CheckoutRouteContext
from plugins.theme_shop.tests.unit.fakes import FakeShopApi
from plugins.theme_shop.tests.unit.test_cart import BARE_LINE, LINE
from plugins.theme_shop.theme_shop.checkout_source import ShopCheckout


def _checkout(shop_api=None, checkout_api=None):
    shop_api = shop_api or FakeShopApi()
    checkout_api = checkout_api or FakeCheckoutApi(default_currency="EUR")
    return ShopCheckout(shop_api.factory, checkout_api.factory), shop_api, checkout_api


def _context(lines=(LINE, BARE_LINE), coupon_code=None):
    return CheckoutRouteContext(
        source="shop", cart_items=tuple(lines), coupon_code=coupon_code
    )


def test_the_source_matches_source_shop_and_posts_the_shop_cart():
    source = _checkout()[0].checkout_source()

    assert source.id == "shop"
    assert source.matches(CheckoutRouteContext(source="shop")) is True
    assert source.matches(CheckoutRouteContext(source="dataset")) is False
    assert source.cart_key == "vbwd_shop_cart"
    assert source.summary_template == "shop/checkout_summary.html.j2"


def test_the_summary_prices_the_cart_lines():
    checkout, _shop_api, _checkout_api = _checkout()

    summary = checkout.load_summary(FakeThemeRequest(), _context())

    assert summary.order_total == Decimal("30")
    assert summary.currency == "EUR"
    assert [line["id"] for line in summary.line_items] == ["p-1", "p-2"]
    assert summary.line_items[0]["price"] == 25.0
    rows = summary.template_context["rows"]
    assert rows[0]["product_id"] == "p-1" and rows[0]["quantity"] == 2
    assert rows[0]["price"].label == "€21.00"


def test_an_empty_cart_is_the_spa_error():
    checkout, _shop_api, _checkout_api = _checkout()

    with pytest.raises(ThemeApiError) as raised:
        checkout.load_summary(FakeThemeRequest(), _context(lines=()))

    assert raised.value.message == "Cart is empty"


def test_a_coupon_is_validated_in_the_ecommerce_scope():
    checkout_api = FakeCheckoutApi(
        default_currency="EUR", validate_coupon={"valid": True, "discount_amount": "3"}
    )
    checkout, _shop_api, _checkout_api = _checkout(checkout_api=checkout_api)

    summary = checkout.load_summary(FakeThemeRequest(), _context(coupon_code="TEN"))

    assert summary.order_total == Decimal("27")
    assert checkout_api.called("validate_coupon") == [
        ("validate_coupon", "TEN", 30.0, "ECOMMERCE")
    ]


def test_submit_posts_the_items_and_answers_the_pending_invoice():
    checkout, shop_api, _checkout_api = _checkout()

    result = checkout.submit(FakeThemeRequest(), _context(coupon_code="TEN"), "invoice")

    assert shop_api.calls[-1] == (
        "cart_checkout",
        {
            "items": [
                {"product_id": "p-1", "quantity": 2, "variant_id": None},
                {"product_id": "p-2", "quantity": 1, "variant_id": "v-9"},
            ],
            "payment_method_code": "invoice",
            "coupon_code": "TEN",
        },
    )
    assert result["invoice"] == {
        "id": "inv-7",
        "invoice_number": "SH-1",
        "status": "PENDING",
        "amount": "99.00",
        "total_amount": "99.00",
    }
