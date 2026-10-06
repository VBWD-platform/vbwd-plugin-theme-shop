"""The ProductDetail CMS component — the twin of ``ProductDetail.vue`` (S152-08).

``GET /api/v1/shop/products/<route slug>``: price, stock, the product-type
specification rows (``GET /api/v1/shop/product-types/<slug>``; an unavailable
type renders none), tags + custom fields, and the exact ``vbwd_shop_cart`` item
``handleAddToCart`` builds (``undefined`` fields left out, as ``JSON.stringify``
does). The runtime adds that item to the cart in the browser.
"""
from typing import Any, Callable, Dict, List, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.price_display import price_display_view
from plugins.theme_cms.theme_cms.tags_custom_fields import tags_and_custom_fields

from .nullish import present_or
from .shop_api import ShopApi

DIGITAL_PRODUCT_TYPE = "digital"
UNLIMITED_QUANTITY = 999
SPEC_YES_KEY = "shop.specYes"
SPEC_NO_KEY = "shop.specNo"
BOOLEAN_FIELD = "boolean"
URL_FIELD = "url"

ApiFactory = Callable[[ThemeRequest], Any]


def _number(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _has_spec_value(value: Any) -> bool:
    """``hasSpecValue``: empty values drop out; ``False`` and ``0`` stay."""
    if value is None or value == "":
        return False
    if isinstance(value, list):
        return len(value) > 0
    return True


def _spec_row(field: Mapping[str, Any], value: Any) -> Dict[str, Any]:
    field_type = field.get("type")
    is_boolean = field_type == BOOLEAN_FIELD
    return {
        "slug": field.get("slug"),
        "label": field.get("label") or "",
        "is_url": field_type == URL_FIELD,
        "boolean_key": (SPEC_YES_KEY if value else SPEC_NO_KEY) if is_boolean else None,
        "display": None
        if is_boolean
        else (
            ", ".join(str(item) for item in value)
            if isinstance(value, list)
            else str(value)
        ),
    }


def _pricing_fields(pricing: Mapping[str, Any]) -> Dict[str, Any]:
    """The S85.4 split threaded into the cart line (absent without a pricing block)."""
    if not pricing:
        return {}
    return {
        "netAmount": _number(pricing.get("net_amount")),
        "grossAmount": _number(pricing.get("gross_amount")),
        "effectiveDisplayMode": pricing.get("effective_display_mode"),
        "pricesDisplayMode": pricing.get("prices_display_mode"),
        "taxes": [
            {
                "code": tax.get("code"),
                "rate": tax.get("rate"),
                "amount": _number(tax.get("amount")),
            }
            for tax in pricing.get("taxes") or []
        ],
    }


def shop_cart_item(
    product: Mapping[str, Any], variant: Optional[Mapping[str, Any]], stock: int
) -> Dict[str, Any]:
    """``handleAddToCart``'s ``CartItem`` (quantity 1)."""
    pricing = product.get("pricing") or {}
    if variant is not None:
        price = _number(
            present_or(variant.get("price_float"), present_or(variant.get("price"), 0))
        )
    else:
        price = _number(
            present_or(pricing.get("gross_amount"), present_or(product.get("price"), 0))
        )
    item = {
        "productId": product.get("id"),
        "productSlug": product.get("slug"),
        "productName": f"{product.get('name')} — {variant.get('name')}"
        if variant
        else product.get("name"),
        "imageUrl": product.get("primary_image_url") or "",
        "price": price,
        "currency": product.get("currency"),
        "quantity": 1,
        "maxQuantity": stock or UNLIMITED_QUANTITY,
        "isDigital": product.get("product_type_slug") == DIGITAL_PRODUCT_TYPE,
        "weight": _number(product.get("weight") or "0"),
        "variantId": (variant or {}).get("id"),
        "variantName": (variant or {}).get("name"),
        **_pricing_fields(pricing),
    }
    return {key: value for key, value in item.items() if value is not None}


class ProductDetail:
    """``build_context(widget_config, page, route_params, theme_request)``."""

    def __init__(self, api_factory: ApiFactory = ShopApi) -> None:
        self._api_factory = api_factory

    def build_context(
        self,
        widget_config: Mapping[str, Any],
        page: Mapping[str, Any],
        route_params: Mapping[str, Any],
        theme_request: ThemeRequest,
    ) -> Dict[str, Any]:
        api = self._api_factory(theme_request)
        try:
            product = api.product(route_params.get("slug") or "")["product"]
        except ThemeApiError as load_error:
            return {"state": "error", "error": load_error.message}
        variants = product.get("variants") or []
        variant = variants[0] if product.get("has_variants") and variants else None
        stock = int((variant or product).get("stock_available") or 0)
        pricing = product.get("pricing") or {}
        price = product.get("price")
        return {
            "state": "product",
            "product": {
                "name": product.get("name") or "",
                "description": product.get("description") or "",
                "image_url": product.get("primary_image_url"),
                "images": product.get("images") or [],
                "price": price_display_view(
                    present_or(pricing.get("net_amount"), price),
                    present_or(pricing.get("gross_amount"), price),
                    product.get("currency"),
                    pricing.get("effective_display_mode"),
                    pricing.get("prices_display_mode"),
                ),
            },
            "in_stock": stock > 0
            or product.get("product_type_slug") == DIGITAL_PRODUCT_TYPE,
            "cart_item": shop_cart_item(product, variant, stock),
            "specifications": self._specifications(api, product),
            "tags_custom_fields": tags_and_custom_fields(product),
        }

    @staticmethod
    def _specifications(api: Any, product: Mapping[str, Any]) -> List[Dict[str, Any]]:
        type_slug = product.get("product_type_slug")
        values = product.get("type_field_values") or {}
        if not type_slug or not values:
            return []
        try:
            product_type = api.product_type(type_slug)["product_type"]
        except ThemeApiError:
            return []
        fields = sorted(
            product_type.get("product_type_fields") or [],
            key=lambda field: field.get("sort_order") or 0,
        )
        return [
            _spec_row(field, values.get(field.get("slug")))
            for field in fields
            if _has_spec_value(values.get(field.get("slug")))
        ]
