"""S152-08 — theme_shop on a real ``create_app`` (theme mode).

The shop-shopping-flow journeys through the themed renderer: the catalogue,
its search fragment and the category route; the product detail with the exact
cart item; the cart island over ``vbwd_shop_cart``; a full themed checkout
(``?source=shop`` → invoice method → confirmation); and the auth-only order
pages, including the GDPR rule (another user's order is "Order not found.").
Products are digital (the ``digital`` product type has no inventory, so the
cart checkout blocks no warehouse stock — there is no admin warehouse API).
"""
import json
import re
import uuid

import pytest

from plugins.theme_cms.tests.integration.cms_seed import unique
from plugins.theme_checkout.tests.integration.themed_stack import (
    FE_USER_ROOT,
    RENDER,
    confirmation_page,
    contract_drift,
    contract_misses,
    ensure_euro_currency,
    ensure_invoice_payment_method,
    post_island,
    regions_html,
    submit_checkout,
    themed_page_gotos,
)

CONFIRMATION = re.compile(r"^/checkout/confirmation\?invoice_id=([0-9a-f-]+)$")
PRODUCT_NAME = "S152-08 Themed Headphones"


def _testid(html, testid):
    return re.search(rf'<[^>]*data-testid="{re.escape(testid)}"[^>]*>', html)


def _cms_page(cms, client, slug, component):
    existing = client.get(f"/api/v1/cms/posts/{slug}")
    if existing.status_code == 200:
        return existing.get_json()
    return cms.page_with_widgets([cms.vue_widget(component)], slug=slug)


@pytest.fixture
def product(client, admin_headers, cms):
    """One active digital product + the three shop CMS pages."""
    ensure_euro_currency(client, admin_headers)
    created = client.post(
        "/api/v1/admin/shop/products",
        json={
            "name": PRODUCT_NAME,
            "slug": f"s152-08-headphones-{uuid.uuid4().hex[:8]}",
            "description": "Seeded by the theme_shop integration tests.",
            "price": 49.0,
            "is_active": True,
            "product_type_slug": "digital",
            "type_field_values": {"license_key": "LIC-S152"},
        },
        headers=admin_headers,
    )
    assert created.status_code == 201, created.get_json()
    for slug, component in (
        ("shop", "ProductGrid"),
        ("shop-product-detail", "ProductDetail"),
        ("shop-cart", "ShoppingCart"),
    ):
        _cms_page(cms, client, slug, component)
    return created.get_json()["product"]


def _cart_item(client, product):
    detail = client.get(f"/shop/product/{product['slug']}", headers=RENDER).get_data(
        as_text=True
    )
    return json.loads(re.search(r"data-vbwd-shop-add='([^']*)'", detail).group(1))


def test_the_catalogue_lists_and_searches_products(client, product):
    page = client.get("/shop", headers=RENDER).get_data(as_text=True)
    hit = client.get(
        "/_render/_fragment/shop/products",
        query_string={"q": "Themed Headphones", "catalog_path": "/shop"},
    ).get_data(as_text=True)
    miss = client.get(
        "/_render/_fragment/shop/products",
        query_string={"q": "zzz-no-such-product", "catalog_path": "/shop"},
    ).get_data(as_text=True)

    assert '<meta name="vbwd-frontend" content="theme">' in page
    assert _testid(page, "product-catalog")
    assert _testid(page, f"product-card-{product['slug']}")
    assert re.search(rf'data-testid="product-card-name">\s*{PRODUCT_NAME}\s*<', hit)
    assert _testid(miss, "product-catalog-empty")


def test_the_category_route_preselects_its_category(client, admin_headers, product):
    category_slug = unique("s152-08-category")
    created = client.post(
        "/api/v1/admin/shop/categories",
        json={"name": "S152-08 Audio", "slug": category_slug},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.get_json()

    html = client.get(f"/shop/category/{category_slug}", headers=RENDER).get_data(
        as_text=True
    )

    assert re.search(rf'<option value="{category_slug}" selected>', html)


def test_the_product_detail_carries_the_cart_item_and_specifications(client, product):
    html = client.get(f"/shop/product/{product['slug']}", headers=RENDER).get_data(
        as_text=True
    )
    item = _cart_item(client, product)

    assert re.search(rf'data-testid="product-detail-name">\s*{PRODUCT_NAME}\s*<', html)
    assert _testid(html, "product-detail-price")
    assert re.search(r'data-testid="product-detail-stock">\s*In Stock\s*<', html)
    assert _testid(html, "product-detail-spec-license_key")
    assert item["productId"] == product["id"] and item["isDigital"] is True
    assert item["quantity"] == 1


def test_the_cart_page_is_an_island_and_its_fragment_renders_the_lines(client, product):
    page = client.get("/shop/cart", headers=RENDER).get_data(as_text=True)
    lines = client.post(
        "/_render/_fragment/shop/cart",
        data={"cart": json.dumps([{**_cart_item(client, product), "quantity": 2}])},
    ).get_data(as_text=True)

    assert _testid(page, "shopping-cart")
    assert 'data-vbwd-cart="vbwd_shop_cart"' in page
    assert _testid(lines, "cart-item")
    assert re.search(r'<span class="cart-item__qty-value">2</span>', lines)


def test_a_full_themed_shop_checkout(client, bearer, admin_headers, cms, product):
    ensure_invoice_payment_method(client, admin_headers)
    confirmation_page(cms, client)
    cart = json.dumps([_cart_item(client, product)])
    fields = {
        "source": "shop",
        "tarif_plan_id": "",
        "cart_type": "",
        "is_cart": "",
        "cart": cart,
    }

    page = client.get("/checkout?source=shop", headers=RENDER).get_data(as_text=True)
    island = post_island(client, bearer, fields)
    submitted = submit_checkout(client, bearer, fields)

    assert 'data-vbwd-cart="vbwd_shop_cart"' in re.search(
        r'<div class="checkout-island"[^>]*>', page
    ).group(0)
    assert re.search(
        rf'data-testid="cart-line-item-{product["id"]}"><span>{PRODUCT_NAME}', island
    )
    assert _testid(island, "payment-method-invoice")
    assert submitted.status_code == 200, submitted.get_data(as_text=True)
    invoice_id = CONFIRMATION.match(submitted.headers["HX-Redirect"]).group(1)
    confirmation = regions_html(
        client, bearer, f"/checkout/confirmation?invoice_id={invoice_id}"
    )
    assert _testid(confirmation, "invoice-details")
    assert re.search(rf'data-testid="line-item-row"><td>{PRODUCT_NAME}', confirmation)
    assert 'data-vbwd-cart-clear="vbwd_shop_cart"' in confirmation


def _paid_order_of(client, headers, admin_headers, product):
    """A shop order of the ``headers`` user: cart checkout, then admin capture."""
    checkout = client.post(
        "/api/v1/shop/cart/checkout",
        json={"items": [{"product_id": product["id"], "quantity": 1}]},
        headers=headers,
    )
    assert checkout.status_code == 201, checkout.get_json()
    paid = client.post(
        f"/api/v1/admin/invoices/{checkout.get_json()['invoice_id']}/mark-paid",
        json={"payment_reference": "S152-08", "payment_method": "manual"},
        headers=admin_headers,
    )
    assert paid.status_code == 200, paid.get_json()
    orders = client.get("/api/v1/shop/orders", headers=headers).get_json()["orders"]
    assert orders, "the paid invoice created no shop order"
    return orders[0]


def test_the_order_pages_are_auth_only_regions(client, bearer, admin_headers, product):
    order = _paid_order_of(client, bearer, admin_headers, product)

    anonymous = client.get("/shop/orders", headers=RENDER).get_data(as_text=True)
    history = regions_html(client, bearer, "/shop/orders")
    detail = regions_html(client, bearer, f"/shop/orders/{order['id']}")

    assert '<body data-auth="pending" data-vbwd-auth-required>' in anonymous
    assert _testid(anonymous, "order-history-loading")
    assert order["order_number"] not in anonymous
    assert re.search(
        rf'data-testid="order-row-number">\s*{order["order_number"]}\s*<', history
    )
    assert re.search(
        rf'data-testid="order-detail-number">\s*Order {order["order_number"]}\s*<',
        detail,
    )
    assert re.search(
        rf'data-testid="order-detail-item-name">\s*{PRODUCT_NAME}\s*<', detail
    )


def test_another_users_order_is_not_found_and_never_listed(
    client, bearer, admin_headers, product
):
    others_order = _paid_order_of(client, admin_headers, admin_headers, product)

    detail = regions_html(client, bearer, f"/shop/orders/{others_order['id']}")
    history = regions_html(client, bearer, "/shop/orders")
    random_detail = regions_html(client, bearer, f"/shop/orders/{uuid.uuid4()}")

    assert re.search(
        r'data-testid="order-detail-empty">\s*Order not found\.\s*<', detail
    )
    assert re.search(
        r'data-testid="order-detail-empty">\s*Order not found\.\s*<', random_detail
    )
    assert others_order["order_number"] not in detail + history


def test_the_order_regions_need_a_bearer(client, product):
    response = client.get(
        "/_render/_fragment/regions", query_string={"path": "/shop/orders"}
    )

    assert response.status_code == 401


# ── e2e DOM contract (shop-shopping-flow fe-user steps + cart.spec) ──────────

SHOPPING_FLOW = "vue/tests/e2e/shop-shopping-flow.spec.ts"
CART_SPEC = "vue/tests/e2e/cart.spec.ts"
SHOP_CONTRACT = [
    (
        '[data-testid="product-catalog"]',
        SHOPPING_FLOW,
        30,
        "catalog",
        r'data-testid="product-catalog"',
    ),
    (
        '[data-testid="product-card-name"]',
        SHOPPING_FLOW,
        33,
        "catalog",
        r'data-testid="product-card-name"',
    ),
    (
        '[data-testid="product-catalog-search"]',
        SHOPPING_FLOW,
        39,
        "catalog",
        r'data-testid="product-catalog-search"',
    ),
    (
        '[data-testid="product-card-name"]',
        SHOPPING_FLOW,
        42,
        "search",
        r'data-testid="product-card-name"',
    ),
    (
        '[data-testid="product-detail"]',
        SHOPPING_FLOW,
        50,
        "detail",
        r'data-testid="product-detail"',
    ),
    (
        '[data-testid="product-detail-name"]',
        SHOPPING_FLOW,
        51,
        "detail",
        r'data-testid="product-detail-name"',
    ),
    (
        '[data-testid="product-detail-price"]',
        SHOPPING_FLOW,
        52,
        "detail",
        r'data-testid="product-detail-price"',
    ),
    (
        '[data-testid="product-detail-add-to-cart"]',
        SHOPPING_FLOW,
        59,
        "detail",
        r'data-testid="product-detail-add-to-cart" data-vbwd-shop-add',
    ),
    (
        '[data-testid="shopping-cart"]',
        SHOPPING_FLOW,
        63,
        "cart_page",
        r'data-testid="shopping-cart"',
    ),
    (
        '[data-testid="cart-item"]',
        SHOPPING_FLOW,
        64,
        "cart_lines",
        r'data-testid="cart-item"',
    ),
    (
        '[data-testid="cart-item-increase"]',
        SHOPPING_FLOW,
        84,
        "cart_lines",
        r'data-testid="cart-item-increase" data-vbwd-shop-quantity="2"',
    ),
    (
        '[data-testid="cart-item-quantity"]',
        SHOPPING_FLOW,
        88,
        "cart_lines",
        r'data-testid="cart-item-quantity"',
    ),
]


def test_every_shop_spec_selector_is_in_the_themed_output(client, product):
    item = _cart_item(client, product)
    outputs = {
        "catalog": client.get("/shop", headers=RENDER).get_data(as_text=True),
        "search": client.get(
            "/_render/_fragment/shop/products",
            query_string={"q": "Headphones", "catalog_path": "/shop"},
        ).get_data(as_text=True),
        "detail": client.get(
            f"/shop/product/{product['slug']}", headers=RENDER
        ).get_data(as_text=True),
        "cart_page": client.get("/shop/cart", headers=RENDER).get_data(as_text=True),
        "cart_lines": client.post(
            "/_render/_fragment/shop/cart", data={"cart": json.dumps([item])}
        ).get_data(as_text=True),
    }

    assert contract_misses(SHOP_CONTRACT, outputs) == []


def test_the_shop_spec_lines_still_use_these_selectors():
    if not (FE_USER_ROOT / SHOPPING_FLOW).is_file():
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")

    assert contract_drift(SHOP_CONTRACT) == []


def test_cart_spec_drives_only_the_spa_dashboard():
    """cart.spec.ts tests the SPA header cart (``/dashboard/*``, never themed, D7)."""
    if not (FE_USER_ROOT / CART_SPEC).is_file():
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")

    assert themed_page_gotos(CART_SPEC) == []
