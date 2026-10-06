"""S152-08 — theme_shop's English catalog never drifts from the SPA's copy.

The fe-user shop plugin has no locale files: its copy is hard-coded English in
the views (plus three keys ``index.ts`` adds with ``addTranslations``). So each
catalog entry names the SPA file it comes from, and must appear there verbatim
(``%(name)s`` ≡ any interpolation). Every requested message is in the catalog
and no entry is unused. The fe-user half skips without fe-user (plugin CI).
"""
import json
import re
from pathlib import Path

import pytest

from plugins.theme_shop.theme_shop import catalog, orders, product_detail
from plugins.theme_shop.theme_shop.plugin_paths import (
    TEMPLATES_DIRECTORY,
    TRANSLATIONS_DIRECTORY,
)

FE_USER_SHOP = (
    Path(__file__).resolve().parents[4].parent / "vbwd-fe-user" / "plugins" / "shop"
)
VIEWS = "shop/views/"
SOURCE_OF_PREFIX = {
    "shop.catalog.": VIEWS + "ProductCatalog.vue",
    "shop.filters.": "../../vbwd-fe-core/src/components/catalogue/CatalogueFilterBar.vue",
    "shop.detail.": VIEWS + "ProductDetail.vue",
    "shop.cart.": VIEWS + "Cart.vue",
    "shop.orders.": VIEWS + "OrderHistory.vue",
    "shop.order.": VIEWS + "OrderDetail.vue",
    "shop.spec": "index.ts",
}
CODE_CHOSEN_KEYS = {label_key for _sort, label_key in catalog.SORT_OPTIONS} | {
    catalog.LOAD_FAILED_KEY,
    orders.LOAD_ORDERS_FAILED_KEY,
    product_detail.SPEC_YES_KEY,
    product_detail.SPEC_NO_KEY,
}
TRANSLATION_CALL = re.compile(r"""_\(\s*'([A-Za-z0-9_.]+)'\s*[,)]""")


def _catalog():
    return json.loads((TRANSLATIONS_DIRECTORY / "en.json").read_text(encoding="utf-8"))


def _template_keys():
    keys = set()
    for template in list(TEMPLATES_DIRECTORY.rglob("*.j2")) + list(
        TEMPLATES_DIRECTORY.rglob("*.js")
    ):
        keys.update(TRANSLATION_CALL.findall(template.read_text(encoding="utf-8")))
        keys.update(
            re.findall(
                r"data-label-key=\"([\w.]+)\"", template.read_text(encoding="utf-8")
            )
        )
    return keys


def test_every_requested_message_is_in_the_catalog():
    assert (_template_keys() | CODE_CHOSEN_KEYS) - set(_catalog()) == set()


def test_the_catalog_has_no_unused_entries():
    assert set(_catalog()) - _template_keys() - CODE_CHOSEN_KEYS == set()


def _source_for(key):
    return next(
        path for prefix, path in SOURCE_OF_PREFIX.items() if key.startswith(prefix)
    )


def test_every_entry_appears_verbatim_in_its_spa_source():
    if not FE_USER_SHOP.is_dir():
        pytest.skip("fe-user is not next to vbwd-backend (plugin CI)")
    drifted = []
    for key, value in _catalog().items():
        source = " ".join(
            (FE_USER_SHOP / _source_for(key)).read_text(encoding="utf-8").split()
        )
        pattern = r"\s*".join(
            ".*?" if part.startswith("%(") else re.escape(part)
            for part in re.split(r"(%\(\w+\)s|\s+)", value)
            if part and not part.isspace()
        )
        if not re.search(pattern, source):
            drifted.append(f"{key}={value!r} not in {_source_for(key)}")

    assert not drifted, drifted
