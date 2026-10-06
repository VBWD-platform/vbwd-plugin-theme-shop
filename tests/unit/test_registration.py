"""S152-08 — what theme_shop registers on enable.

The four CMS-layout routes (fe-user mounts them as ``CmsPage`` with fixed slugs
``shop`` / ``shop-product-detail`` / ``shop-cart``) render those CMS pages with
the route params in context; the two auth-only order pages; the catalogue and
cart fragments; the four widget twins into theme_cms and the ``shop`` checkout
source into theme_checkout. Everything is owned by fe-user ``shop``.
"""
from pathlib import Path
from types import MappingProxyType, SimpleNamespace

import pytest
from flask import Flask

from plugins.theme import ThemePlugin
from plugins.theme.theme.page_registry import USER_PAGE
from plugins.theme_checkout import ThemeCheckoutPlugin
from plugins.theme_checkout.theme_checkout.checkout_sources import CheckoutRouteContext
from plugins.theme_cms import ThemeCmsPlugin
from plugins.theme_cms.theme_cms.pages import DISPATCH_TEMPLATE
from plugins.theme_shop import ThemeShopPlugin
from plugins.theme_shop.theme_shop.plugin_paths import (
    STYLESHEETS_DIRECTORY,
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)
from plugins.theme_shop.theme_shop.registration import shop_pages

FE_USER_SHOP_INDEX = (
    Path(__file__).resolve().parents[5]
    / "vbwd-fe-user"
    / "plugins"
    / "shop"
    / "index.ts"
)
CMS_ROUTES = {
    "/shop": "shop",
    "/shop/category/<slug>": "shop",
    "/shop/product/<slug>": "shop-product-detail",
    "/shop/cart": "shop-cart",
}


def _app(plugins):
    app = Flask(__name__)
    app.plugin_manager = SimpleNamespace(get_plugin=plugins.get)
    return app


@pytest.fixture
def enabled(monkeypatch, tmp_path):
    monkeypatch.setenv("VBWD_VAR_DIR", str(tmp_path / "var"))
    plugins = {
        "theme": ThemePlugin(),
        "theme_cms": ThemeCmsPlugin(),
        "theme_checkout": ThemeCheckoutPlugin(),
        "theme_shop": ThemeShopPlugin(),
    }
    with _app(plugins).app_context():
        for plugin in plugins.values():
            plugin.on_enable()
        yield SimpleNamespace(**plugins)


def test_registers_the_six_shop_routes(enabled):
    pages = {page.rule: page for page in enabled.theme.page_registry.pages()}

    for rule in CMS_ROUTES:
        assert pages[rule].owner_fe_user_plugin == "shop", rule
        assert pages[rule].template == DISPATCH_TEMPLATE
    assert pages["/shop/orders"].template == "shop/orders.html.j2"
    assert pages["/shop/orders/<order_id>"].template == "shop/order_detail.html.j2"
    assert pages["/shop/orders"].auth == USER_PAGE


def test_each_cms_route_renders_its_cms_page_with_the_route_params():
    rendered = []
    fake_cms_pages = SimpleNamespace(
        cms_slug_page_context=lambda request, slug: rendered.append(
            (slug, dict(request.view_args))
        )
        or {}
    )
    pages = {page.rule: page for page in shop_pages(fake_cms_pages)}

    for rule in CMS_ROUTES:
        pages[rule].build_context(
            SimpleNamespace(view_args=MappingProxyType({"slug": "x"}))
        )

    assert rendered == [(slug, {"slug": "x"}) for slug in CMS_ROUTES.values()]


def test_registers_the_catalogue_and_cart_fragments(enabled):
    fragments = {
        fragment.rule: fragment
        for fragment in enabled.theme.fragment_registry.fragments()
    }

    assert fragments["/_render/_fragment/shop/products"].methods == ("GET",)
    assert fragments["/_render/_fragment/shop/cart"].methods == ("POST",)
    assert {
        fragment.owner_fe_user_plugin
        for rule, fragment in fragments.items()
        if "/shop/" in rule
    } == {"shop"}


def test_registers_the_widget_twins_and_the_checkout_source(enabled):
    for name in ("ProductGrid", "ProductDetail", "ShoppingCart", "CartBadge"):
        assert enabled.theme_cms.component_registry.resolve(name) is not None, name
    source = enabled.theme_checkout.source_registry.find(
        CheckoutRouteContext(source="shop")
    )
    assert source.id == "shop"


def test_contributes_templates_translations_and_stylesheets(enabled):
    registry = enabled.theme.theme_registry

    assert TEMPLATES_DIRECTORY in registry.contributed_template_paths()
    assert TRANSLATIONS_DIRECTORY in registry.contributed_translation_paths()
    assert STYLESHEETS_DIRECTORY in registry.contributed_stylesheet_paths()


def test_enabling_twice_registers_once(enabled):
    with _app(vars(enabled)).app_context():
        enabled.theme_shop.on_enable()

    assert [page.rule for page in enabled.theme.page_registry.pages()].count(
        "/shop"
    ) == 1


def test_the_routes_and_widgets_are_the_ones_fe_user_registers():
    if not FE_USER_SHOP_INDEX.is_file():
        pytest.skip("fe-user shop plugin is not next to vbwd-backend (plugin CI)")
    source = FE_USER_SHOP_INDEX.read_text(encoding="utf-8")

    for path in (
        "/shop",
        "/shop/category/:slug",
        "/shop/product/:slug",
        "/shop/cart",
        "/shop/orders",
        "/shop/orders/:id",
    ):
        assert f"path: '{path}'" in source
    for slug in set(CMS_ROUTES.values()):
        assert f"props: {{ slug: '{slug}' }}" in source
    for name in ("ProductGrid", "ProductDetail", "ShoppingCart", "CartBadge"):
        assert f"registerCmsVueComponent('{name}'" in source
