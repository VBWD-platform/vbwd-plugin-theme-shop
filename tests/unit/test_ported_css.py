"""S152-08 — the SPA's structural CSS for the shop views.

S152-06c rules (theme ``tests/css_inventory`` helpers): every class a theme_shop
template or runtime uses that the mirrored Vue component styles has a ported
rule, no invented rule. S152-06d colour tokens (theme ``tests/colour_tokens``): a
literal colour appears only as the fallback of a ``var(--vbwd-…, <literal>)``
token; every SPA colour of a used rule is ported with its exact literal; every
``--vbwd-shop-*`` token is documented in the theme guide. The SPA-comparing half
skips without fe-user.
"""
from pathlib import Path

import pytest

from plugins.theme.theme.theme_registry import TOKEN_NAME_PATTERN
from plugins.theme.tests.colour_tokens import (
    adapter_token_fallbacks,
    documented_colour_tokens,
    token_fallback_mismatches,
    unported_spa_colours,
)
from plugins.theme.tests.css_inventory import (
    hard_coded_colours,
    is_used,
    rule_classes,
    script_classes,
    template_class_usage,
    vue_style_text,
)
from plugins.theme_shop.theme_shop.plugin_paths import (
    STYLESHEETS_DIRECTORY,
    TEMPLATES_DIRECTORY,
)

BACKEND_ROOT = Path(__file__).resolve().parents[4]
SHOP_SOURCE = BACKEND_ROOT.parent / "vbwd-fe-user" / "plugins" / "shop" / "shop"
SOURCE_STYLE_FILES = (
    SHOP_SOURCE / "views" / "ProductCatalog.vue",
    SHOP_SOURCE / "views" / "ProductDetail.vue",
    SHOP_SOURCE / "views" / "Cart.vue",
    SHOP_SOURCE / "views" / "OrderHistory.vue",
    SHOP_SOURCE / "views" / "OrderDetail.vue",
    SHOP_SOURCE / "components" / "CartBadge.vue",
    SHOP_SOURCE / "components" / "ShopCheckoutSummary.vue",
)

ADAPTER = "shop"

needs_spa_checkouts = pytest.mark.skipif(
    not SHOP_SOURCE.is_dir(),
    reason="the fe-user checkout is not next to vbwd-backend",
)


def _ported_css():
    return "\n".join(
        path.read_text(encoding="utf-8")
        for path in sorted(STYLESHEETS_DIRECTORY.rglob("*.css"))
    )


def _used_styled_classes():
    static_classes, prefixes = template_class_usage(TEMPLATES_DIRECTORY.rglob("*.j2"))
    static_classes |= script_classes(TEMPLATES_DIRECTORY.rglob("*.js"))
    source_classes = set()
    for source in SOURCE_STYLE_FILES:
        source_classes |= rule_classes(
            vue_style_text(source.read_text(encoding="utf-8"))
        )
    return {name for name in source_classes if is_used(name, static_classes, prefixes)}


@needs_spa_checkouts
def test_every_used_styled_class_has_a_ported_rule():
    assert _used_styled_classes() - rule_classes(_ported_css()) == set()


@needs_spa_checkouts
def test_every_ported_class_is_used_and_styled_in_the_spa():
    assert rule_classes(_ported_css()) - _used_styled_classes() == set()


def test_the_ported_css_styles_the_storefront():
    ported = rule_classes(_ported_css())

    for class_name in (
        "product-card",
        "product-detail",
        "cart-item",
        "order-row__link",
        "cart-badge",
    ):
        assert class_name in ported


def test_the_ported_css_carries_no_hard_coded_colour():
    assert hard_coded_colours(_ported_css()) == []


@needs_spa_checkouts
def test_every_spa_colour_of_a_used_rule_is_ported_with_its_literal():
    assert (
        unported_spa_colours(SOURCE_STYLE_FILES, _ported_css(), _used_styled_classes())
        == []
    )


@needs_spa_checkouts
def test_every_shop_token_fallback_is_the_spa_literal():
    assert token_fallback_mismatches(SOURCE_STYLE_FILES, _ported_css(), ADAPTER) == []


def test_every_shop_token_is_documented_with_its_default_and_vice_versa():
    used = {
        token: sorted(fallbacks)
        for token, fallbacks in adapter_token_fallbacks(_ported_css(), ADAPTER).items()
    }
    documented = {
        token: [default] for token, default in documented_colour_tokens(ADAPTER).items()
    }

    assert used and used == documented


def test_every_shop_token_is_a_tokens_json_name():
    tokens = adapter_token_fallbacks(_ported_css(), ADAPTER)

    assert [name for name in tokens if not TOKEN_NAME_PATTERN.match(name)] == []
