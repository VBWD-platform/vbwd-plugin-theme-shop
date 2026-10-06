"""S152-08 — theme_shop markup keeps the SPA's DOM contract (D2).

``ProductCatalog.vue`` (+ fe-core ``CatalogueFilterBar``), ``ProductDetail.vue``,
``Cart.vue``, ``CartBadge.vue``, ``OrderHistory.vue``, ``OrderDetail.vue`` and
``ShopCheckoutSummary.vue``: same testids, classes and English copy, plus the
runtime hooks (``data-vbwd-shop-add``, ``data-vbwd-cart="vbwd_shop_cart"``,
``data-vbwd-shop-quantity`` / ``-remove``, the badge) and the auth-only shell of
the order pages (``data-auth="pending"``, personalised regions).
"""
import json
import re

import pytest

from plugins.theme.theme.viewer import Viewer
from plugins.theme_checkout.tests.unit.fakes import FakeCheckoutApi, FakeThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_sources import CheckoutRouteContext
from plugins.theme_shop.tests.unit.fakes import FakeShopApi
from plugins.theme_shop.tests.unit.template_harness import render, theme_plugin
from plugins.theme_shop.tests.unit.test_cart import BARE_LINE, LINE
from plugins.theme_shop.tests.unit.test_product_detail import VARIANT_PRODUCT
from plugins.theme_shop.theme_shop.cart import ShoppingCart
from plugins.theme_shop.theme_shop.catalog import ProductGrid
from plugins.theme_shop.theme_shop.checkout_source import ShopCheckout
from plugins.theme_shop.theme_shop.orders import OrderDetailPage, OrderHistoryPage
from plugins.theme_shop.theme_shop.product_detail import ProductDetail

VIEWER = Viewer(user_id="user-a", access_level_slugs=frozenset(), permissions=())


@pytest.fixture(scope="module")
def plugin():
    return theme_plugin()


@pytest.fixture(autouse=True)
def isolated_var_directory(tmp_path, monkeypatch):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))


def _testid(html, testid):
    return re.search(rf'<[^>]*data-testid="{re.escape(testid)}"[^>]*>', html)


def _component(plugin, template, context):
    return render(plugin, template, {"component_context": context})


def test_the_catalog_renders_toolbar_filters_cards_and_pager(plugin):
    context = ProductGrid(
        FakeShopApi(
            products={"items": FakeShopApi().answers["products"]["items"], "pages": 2}
        ).factory
    ).build_context({}, {}, {}, FakeThemeRequest({"tags": "wireless"}))

    html = _component(plugin, "shop/components/product_grid.html.j2", context)

    assert re.search(
        r'<div class="product-catalog" data-testid="product-catalog">', html
    )
    assert re.search(r'<h1 class="product-catalog__heading">\s*Shop\s*</h1>', html)
    search = _testid(html, "product-catalog-search").group(0)
    assert (
        'placeholder="Search products..."' in search
        and 'id="product-catalog-search"' in search
    )
    assert 'hx-get="/_render/_fragment/shop/products"' in search
    for label in (
        "Newest",
        "Name A–Z",
        "Name Z–A",
        "Price: Low → High",
        "Price: High → Low",
    ):
        assert f">{label}</option>" in html
    assert _testid(html, "catalogue-filter-bar")
    assert _testid(html, "catalogue-facet-select-category")
    assert re.search(
        r'data-testid="catalogue-facet-chip-tags-wireless"[^>]*>Wireless<', html
    )
    card = re.search(
        r'<a href="/shop/product/wireless-headphones-pro" class="product-card" '
        r'data-testid="product-card-wireless-headphones-pro">',
        html,
    )
    assert card
    assert re.search(
        r'data-testid="product-card-name">\s*Wireless Headphones Pro\s*<', html
    )
    assert _testid(html, "product-card-price")
    assert 'class="product-card__tag product-card__tag--active"' in html
    assert _testid(html, "product-catalog-pager") and _testid(
        html, "product-catalog-next"
    )
    assert re.search(r'data-testid="product-catalog-prev"[^>]*disabled', html)


def test_catalog_empty_and_error_copy(plugin):
    empty = ProductGrid(
        FakeShopApi(products={"items": [], "pages": 1}).factory
    ).build_context({}, {}, {}, FakeThemeRequest())

    html = _component(plugin, "shop/components/product_grid.html.j2", empty)

    assert re.search(
        r'data-testid="product-catalog-empty">\s*No products found\.\s*<', html
    )


def test_the_product_detail_renders_the_add_to_cart_island(plugin):
    context = ProductDetail(
        FakeShopApi(product={"product": VARIANT_PRODUCT}).factory
    ).build_context({}, {}, {"slug": "wireless-headphones-pro"}, FakeThemeRequest())
    in_stock = ProductDetail(FakeShopApi().factory).build_context(
        {}, {}, {"slug": "wireless-headphones-pro"}, FakeThemeRequest()
    )

    sold_out_html = _component(
        plugin, "shop/components/product_detail.html.j2", context
    )
    html = _component(plugin, "shop/components/product_detail.html.j2", in_stock)

    assert re.search(r'<div class="product-detail" data-testid="product-detail">', html)
    for testid in (
        "product-detail-image",
        "product-detail-thumbnails",
        "product-detail-name",
        "product-detail-price",
        "product-detail-description",
        "product-detail-stock",
    ):
        assert _testid(html, testid), testid
    assert re.search(r'data-testid="product-detail-stock">\s*In Stock\s*<', html)
    button = _testid(html, "product-detail-add-to-cart").group(0)
    assert "disabled" not in button
    item = json.loads(
        re.search(r"data-vbwd-shop-add='([^']*)'", button)
        .group(1)
        .replace("&#34;", '"')
    )
    assert item["productId"] == "p-1"
    assert re.search(
        r'data-testid="product-detail-add-to-cart"[^>]*>\s*Add to Cart\s*<', html
    )
    view_cart = _testid(html, "product-detail-view-cart").group(0)
    assert "hidden" in view_cart and 'href="/shop/cart"' in view_cart
    assert re.search(
        r'data-testid="product-detail-stock">\s*Out of Stock\s*<', sold_out_html
    )
    assert "disabled" in _testid(sold_out_html, "product-detail-add-to-cart").group(0)


def test_a_product_error_renders_its_message(plugin):
    from plugins.theme.theme.theme_api import ThemeApiError

    context = ProductDetail(
        FakeShopApi(product=ThemeApiError(404, "Product not found")).factory
    ).build_context({}, {}, {"slug": "x"}, FakeThemeRequest())

    html = _component(plugin, "shop/components/product_detail.html.j2", context)

    assert re.search(
        r'data-testid="product-detail-error">\s*Product not found\s*<', html
    )


def test_the_shopping_cart_is_an_island_over_the_shop_cart(plugin):
    html = _component(plugin, "shop/components/shopping_cart.html.j2", {})

    assert re.search(r'<div class="shopping-cart" data-testid="shopping-cart">', html)
    assert re.search(
        r'<h1 class="shopping-cart__heading">\s*Shopping Cart\s*</h1>', html
    )
    island = re.search(r'<div[^>]*data-vbwd-cart="vbwd_shop_cart"[^>]*>', html).group(0)
    assert 'hx-post="/_render/_fragment/shop/cart"' in island
    assert "vbwd:cart-changed from:document" in island
    assert re.search(
        r'data-testid="shopping-cart-loading">\s*Loading cart\.\.\.\s*<', html
    )


def test_the_cart_fragment_renders_lines_controls_and_footer(plugin):
    context = ShoppingCart(
        FakeCheckoutApi(default_currency="EUR").factory
    ).fragment_context(FakeThemeRequest({"cart": json.dumps([LINE, BARE_LINE])}))

    html = render(plugin, "shop/_cart_fragment.html.j2", context)

    assert html.count('data-testid="cart-item"') == 2
    assert re.search(r'data-testid="cart-item-name">\s*Mug\s*<', html)
    assert '<span class="cart-item__variant">2m</span>' in html
    assert re.search(
        r'data-testid="cart-item-quantity"[^>]*>.*?<span class="cart-item__qty-value">2</span>',
        html,
        re.S,
    )
    assert re.search(r'data-testid="cart-item-increase"[^>]*disabled', html)
    decrease = re.findall(r'<button[^>]*data-testid="cart-item-decrease"[^>]*>', html)[
        1
    ]
    assert "disabled" in decrease
    increase = re.findall(r'<button[^>]*data-testid="cart-item-increase"[^>]*>', html)[
        1
    ]
    assert (
        'data-vbwd-shop-quantity="2"' in increase
        and 'data-variant-id="v-9"' in increase
    )
    assert re.search(r'data-testid="cart-item-remove"[^>]*>\s*Remove\s*<', html)
    assert re.search(r"Subtotal \(3 items\):", html)
    form = re.search(
        r'<form method="get" action="/checkout">(.*?)</form>', html, re.S
    ).group(1)
    assert '<input type="hidden" name="source" value="shop">' in form
    assert re.search(
        r'data-testid="shopping-cart-checkout"[^>]*>\s*Proceed to Checkout\s*<', form
    )


def test_the_empty_cart_links_back_to_the_shop(plugin):
    html = render(plugin, "shop/_cart_fragment.html.j2", {"state": "empty"})

    assert re.search(
        r'data-testid="shopping-cart-empty">\s*<p>Your cart is empty\.</p>', html
    )
    assert re.search(
        r'<a href="/shop" class="shopping-cart__browse-link" '
        r'data-testid="shopping-cart-browse">\s*Browse Products\s*</a>',
        html,
    )


def test_the_cart_badge_is_a_client_island(plugin):
    html = _component(plugin, "shop/components/cart_badge.html.j2", {})

    badge = _testid(html, "cart-badge").group(0)
    assert 'href="/shop/cart"' in badge and "hidden" in badge
    assert "data-vbwd-shop-cart-badge" in badge
    assert '<span class="cart-badge__count"></span>' in html


def test_the_order_history_page_is_auth_only_with_the_orders_as_a_region(plugin):
    anonymous = render(
        plugin,
        "shop/orders.html.j2",
        OrderHistoryPage(FakeShopApi().factory).context(FakeThemeRequest()),
    )
    viewer = render(
        plugin,
        "shop/orders.html.j2",
        OrderHistoryPage(FakeShopApi().factory).context(
            FakeThemeRequest(user_id="user-a")
        ),
        viewer=VIEWER,
    )

    assert '<body data-auth="pending" data-vbwd-auth-required>' in anonymous
    assert '<div class="vbwd-private-chrome">' in anonymous
    assert re.search(
        r'<h1 class="order-history__heading">\s*Order History\s*</h1>', anonymous
    )
    assert 'data-vbwd-region="r1"' in anonymous
    assert re.search(
        r'data-testid="order-history-loading">\s*Loading orders\.\.\.\s*<', anonymous
    )
    assert "ORD-1" not in anonymous
    assert re.search(r'data-testid="order-row-number">\s*ORD-1\s*<', viewer)
    assert 'class="order-row__status order-row__status--pending"' in viewer


def test_the_order_detail_page_shows_not_found_like_the_spa(plugin):
    from plugins.theme.theme.theme_api import ThemeApiError

    context = OrderDetailPage(
        FakeShopApi(order=ThemeApiError(403, "Forbidden")).factory
    ).context(
        FakeThemeRequest(
            view_args={"order_id": "11111111-1111-1111-1111-111111111111"},
            user_id="user-a",
        )
    )

    html = render(plugin, "shop/order_detail.html.j2", context, viewer=VIEWER)

    assert re.search(r'data-testid="order-detail-empty">\s*Order not found\.\s*<', html)


def test_the_order_detail_page_shows_the_order(plugin):
    context = OrderDetailPage(FakeShopApi().factory).context(
        FakeThemeRequest(
            view_args={"order_id": "11111111-1111-1111-1111-111111111111"},
            user_id="user-a",
        )
    )

    html = render(plugin, "shop/order_detail.html.j2", context, viewer=VIEWER)

    assert re.search(r'data-testid="order-detail-number">\s*Order ORD-1\s*<', html)
    assert re.search(r'data-testid="order-detail-item-name">\s*Cable\s*<', html)
    assert re.search(r'data-testid="order-detail-total">\s*Total:\s*€99\.00\s*<', html)
    assert re.search(
        r'data-testid="order-detail-date">\s*Placed on October 4, 2026\s*<', html
    )


def test_the_checkout_summary_lists_the_cart_lines(plugin):
    summary = ShopCheckout(
        FakeShopApi().factory, FakeCheckoutApi(default_currency="EUR").factory
    ).load_summary(
        FakeThemeRequest(),
        CheckoutRouteContext(source="shop", cart_items=(LINE, BARE_LINE)),
    )

    html = render(
        plugin,
        "shop/checkout_summary.html.j2",
        {"summary": {"line_items": summary.line_items, **summary.template_context}},
    )

    assert '<div class="cart-items-summary">' in html
    assert re.search(
        r'data-testid="cart-line-item-p-1"><span>Mug\s*<span class="plan-description">x2</span></span>',
        html,
    )
    assert re.search(r'data-testid="cart-line-item-p-2"><span>Cable</span>', html)
