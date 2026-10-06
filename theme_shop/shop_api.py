"""The public shop API the fe-user plugin calls, always through core C2 (D3).

One method per ``/api/v1/shop/*`` endpoint the shop views and checkout source
use. A facet ``options_endpoint`` from ``/shop/filters`` is absolute
(``/api/v1/shop/categories``); ProductCatalog.vue strips ``/api/v1`` because its
client prepends it, while ``call_api`` takes the full path — so an absolute
endpoint is used as is and a relative one gets the prefix exactly once.
"""
from typing import Any, Mapping
from urllib.parse import quote

from plugins.theme.theme.theme_api import call_api
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_cms.theme_cms.components.catalogue_filters import (
    API_PREFIX,
    options_api_path,
)

SHOP_API_PREFIX = f"{API_PREFIX}/shop"


def _segment(value: str) -> str:
    return quote(value, safe="")


class ShopApi:
    """The shop endpoints for one themed request."""

    def __init__(self, theme_request: ThemeRequest) -> None:
        self._theme_request = theme_request

    def _get(self, path: str, **options: Any) -> Any:
        return call_api(self._theme_request, "GET", path, **options)

    def filters(self) -> Any:
        return self._get(f"{SHOP_API_PREFIX}/filters")

    def options(self, endpoint: str) -> Any:
        return self._get(options_api_path(endpoint))

    def products(self, query: Mapping[str, Any]) -> Any:
        return self._get(f"{SHOP_API_PREFIX}/products", query=dict(query))

    def product(self, slug: str) -> Any:
        return self._get(f"{SHOP_API_PREFIX}/products/{_segment(slug)}")

    def product_type(self, slug: str) -> Any:
        return self._get(f"{SHOP_API_PREFIX}/product-types/{_segment(slug)}")

    def orders(self) -> Any:
        return self._get(f"{SHOP_API_PREFIX}/orders")

    def order(self, order_id: str) -> Any:
        return self._get(f"{SHOP_API_PREFIX}/orders/{_segment(order_id)}")

    def cart_checkout(self, payload: Mapping[str, Any]) -> Any:
        return call_api(
            self._theme_request,
            "POST",
            f"{SHOP_API_PREFIX}/cart/checkout",
            json=dict(payload),
        )
