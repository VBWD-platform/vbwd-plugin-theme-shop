"""S152-08 — the public shop endpoints, always through core C2 (D3).

The facet descriptor names absolute ``options_endpoint`` paths
(``/api/v1/shop/categories``). ProductCatalog.vue strips ``/api/v1`` because its
axios client prepends it; ``call_api`` takes the FULL path and refuses anything
outside ``/api/v1/``, so the themed client keeps an absolute endpoint as is and
prefixes a relative one — never doubling the prefix (cf. the S152-00 bug).
"""
import pytest

from plugins.theme_checkout.tests.unit.fakes import FakeThemeRequest, ScriptedApi
from plugins.theme_shop.theme_shop import shop_api
from plugins.theme_shop.theme_shop.shop_api import ShopApi


@pytest.fixture
def scripted(monkeypatch):
    api = ScriptedApi(
        {
            ("GET", "/api/v1/shop/categories"): {"categories": []},
            ("GET", "/api/v1/shop/filters"): {"facets": []},
            ("GET", "/api/v1/shop/products"): {"items": []},
            ("GET", "/api/v1/shop/products/mug%20cup"): {"product": {}},
            ("GET", "/api/v1/shop/product-types/digital"): {"product_type": {}},
            ("GET", "/api/v1/shop/orders"): {"orders": []},
            ("GET", "/api/v1/shop/orders/o-1"): {"order": {}},
            ("POST", "/api/v1/shop/cart/checkout"): {"invoice_id": "i"},
        }
    )
    monkeypatch.setattr(shop_api, "call_api", api)
    return api


@pytest.mark.parametrize(
    "endpoint", ["/api/v1/shop/categories", "/shop/categories", "shop/categories"]
)
def test_an_options_endpoint_resolves_to_one_api_path(scripted, endpoint):
    ShopApi(FakeThemeRequest()).options(endpoint)

    assert scripted.paths() == [("GET", "/api/v1/shop/categories")]


def test_each_method_calls_the_endpoint_the_spa_calls(scripted):
    api = ShopApi(FakeThemeRequest())

    api.filters()
    api.products({"page": 1, "per_page": 12})
    api.product("mug cup")
    api.product_type("digital")
    api.orders()
    api.order("o-1")
    api.cart_checkout({"items": []})

    assert scripted.paths() == [
        ("GET", "/api/v1/shop/filters"),
        ("GET", "/api/v1/shop/products"),
        ("GET", "/api/v1/shop/products/mug%20cup"),
        ("GET", "/api/v1/shop/product-types/digital"),
        ("GET", "/api/v1/shop/orders"),
        ("GET", "/api/v1/shop/orders/o-1"),
        ("POST", "/api/v1/shop/cart/checkout"),
    ]
    assert scripted.calls[1][2] == {"query": {"page": 1, "per_page": 12}}
    assert scripted.calls[-1][2] == {"json": {"items": []}}
