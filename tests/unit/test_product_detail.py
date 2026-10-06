"""S152-08 — the ProductDetail CMS component, the twin of ``ProductDetail.vue``.

``GET /api/v1/shop/products/<route slug>``: price, stock (first variant or the
product; digital products are always in stock), the product-type specification
rows (``GET /api/v1/shop/product-types/<slug>``), tags + custom fields and the
exact ``vbwd_shop_cart`` item ``handleAddToCart`` builds — checked against the
theme runtime's SPA storage contract fixture.
"""
import re
from pathlib import Path

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_checkout.tests.unit.fakes import FakeThemeRequest
from plugins.theme_shop.tests.unit.fakes import PRODUCT, FakeShopApi
from plugins.theme_shop.theme_shop.product_detail import ProductDetail

STORAGE_CONTRACT = (
    Path(__file__).resolve().parents[3]
    / "theme"
    / "tests"
    / "js"
    / "fixtures"
    / "spa_storage_contract.mjs"
)
VARIANT_PRODUCT = {
    **PRODUCT,
    "has_variants": True,
    "variants": [
        {
            "id": "v-1",
            "name": "Blue",
            "price": "89.00",
            "price_float": 89.0,
            "stock_available": 0,
        },
    ],
}
DIGITAL_TYPE = {
    "product_type": {
        "slug": "digital",
        "product_type_fields": [
            {"slug": "format", "type": "string", "label": "Format", "sort_order": 2},
            {"slug": "drm", "type": "boolean", "label": "DRM", "sort_order": 1},
            {"slug": "site", "type": "url", "label": "Site", "sort_order": 3},
            {"slug": "empty", "type": "string", "label": "Empty", "sort_order": 4},
        ],
    }
}


def _detail(product=PRODUCT, **answers):
    api = FakeShopApi(product={"product": product}, **answers)
    context = ProductDetail(api.factory).build_context(
        {}, {}, {"slug": product["slug"]}, FakeThemeRequest()
    )
    return context, api


def _shop_cart_item_keys():
    source = STORAGE_CONTRACT.read_text(encoding="utf-8")
    block = source[source.index("SHOP_CART_ITEMS") :]
    return set(re.findall(r"^    (\w+):", block, re.MULTILINE))


def test_the_product_is_read_by_the_route_slug():
    context, api = _detail()

    assert api.calls[0] == ("product", "wireless-headphones-pro")
    assert context["state"] == "product"
    assert context["product"]["price"].label == "€99.00"
    assert context["in_stock"] is True


def test_the_cart_item_is_the_spa_shape():
    context, _api = _detail({**VARIANT_PRODUCT, "currency": "EUR"})

    item = context["cart_item"]
    assert set(item) == _shop_cart_item_keys()
    assert item["productName"] == "Wireless Headphones Pro — Blue"
    assert item["price"] == 89.0
    assert item["variantId"] == "v-1"
    assert item["taxes"] == [{"code": "VAT", "rate": "19", "amount": 15.81}]
    assert item["netAmount"] == 83.19 and item["grossAmount"] == 99.0


def test_without_a_variant_the_charge_is_the_gross_and_absent_keys_are_dropped():
    context, _api = _detail()

    item = context["cart_item"]
    assert item["price"] == 99.0
    assert item["maxQuantity"] == 5
    assert item["weight"] == 0.3
    assert "variantId" not in item and "variantName" not in item
    assert "currency" not in item


def test_a_sold_out_first_variant_is_out_of_stock_but_digital_never_is():
    sold_out, _api = _detail(VARIANT_PRODUCT)
    digital, _api = _detail(
        {**PRODUCT, "stock_available": 0, "product_type_slug": "digital"},
        product_type=DIGITAL_TYPE,
    )

    assert sold_out["in_stock"] is False
    assert sold_out["cart_item"]["maxQuantity"] == 999
    assert digital["in_stock"] is True


def test_specification_rows_follow_the_type_order_and_formatting():
    context, api = _detail(
        {
            **PRODUCT,
            "product_type_slug": "digital",
            "type_field_values": {
                "format": ["PDF", "EPUB"],
                "drm": False,
                "site": "https://x.example",
            },
        },
        product_type=DIGITAL_TYPE,
    )

    assert ("product_type", "digital") in api.calls
    assert [(row["slug"], row["display"]) for row in context["specifications"]] == [
        ("drm", None),
        ("format", "PDF, EPUB"),
        ("site", "https://x.example"),
    ]
    assert context["specifications"][0]["boolean_key"] == "shop.specNo"
    assert context["specifications"][2]["is_url"] is True


def test_an_unavailable_product_type_renders_no_specifications():
    context, _api = _detail(
        {**PRODUCT, "product_type_slug": "gone", "type_field_values": {"a": 1}},
        product_type=ThemeApiError(404, "Product type not found"),
    )

    assert context["specifications"] == []


def test_an_unknown_product_shows_the_api_error():
    api = FakeShopApi(product=ThemeApiError(404, "Product not found"))

    context = ProductDetail(api.factory).build_context(
        {}, {}, {"slug": "x"}, FakeThemeRequest()
    )

    assert context == {"state": "error", "error": "Product not found"}
