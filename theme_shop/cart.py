"""The ShoppingCart island — the twin of ``Cart.vue`` (S152-08).

The page cannot know the browser's ``vbwd_shop_cart``: the island posts it
(``data-vbwd-cart``) and this fragment renders the lines exactly as the SPA
renders its stored lines — net/gross per line falling back to the bare price,
the line's currency else the operating one (``GET /api/v1/config``, as
``useAppConfigStore``). The footer subtotal is the gross sum (no display modes).
"""
import json
from typing import Any, Callable, Dict, List, Mapping, Tuple

from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_api import CheckoutApi
from plugins.theme_checkout.theme_checkout.price_display import price_display_view

from .nullish import present_or

CART_FIELD = "cart"
MINIMUM_QUANTITY = 1

ApiFactory = Callable[[ThemeRequest], Any]
CartLine = Mapping[str, Any]


def posted_shop_cart(raw_cart: Any) -> List[CartLine]:
    """The posted ``vbwd_shop_cart`` (a bare JSON array, like the store); else empty."""
    try:
        items = json.loads(raw_cart or "[]")
    except (TypeError, ValueError):
        return []
    return (
        [item for item in items if isinstance(item, dict)]
        if isinstance(items, list)
        else []
    )


def line_amounts(line: CartLine) -> Tuple[float, float]:
    """``lineNet`` / ``lineGross`` per unit: the split, else the bare price."""
    price = float(line.get("price") or 0)
    return (
        float(present_or(line.get("netAmount"), price)),
        float(present_or(line.get("grossAmount"), price)),
    )


def _line_view(line: CartLine, currency: str) -> Dict[str, Any]:
    net, gross = line_amounts(line)
    quantity = int(line.get("quantity") or MINIMUM_QUANTITY)
    modes = (line.get("effectiveDisplayMode"), line.get("pricesDisplayMode"))
    return {
        "product_id": line.get("productId") or "",
        "variant_id": line.get("variantId") or "",
        "name": line.get("productName") or "",
        "variant_name": line.get("variantName") or "",
        "image_url": line.get("imageUrl") or "",
        "quantity": quantity,
        "unit_price": price_display_view(net, gross, currency, *modes),
        "subtotal": price_display_view(
            net * quantity, gross * quantity, currency, *modes
        ),
        "can_decrease": quantity > MINIMUM_QUANTITY,
        "can_increase": quantity < int(line.get("maxQuantity") or quantity),
        "decrease_to": quantity - 1,
        "increase_to": quantity + 1,
    }


class ShoppingCart:
    """The cart island fragment's context."""

    def __init__(self, checkout_api_factory: ApiFactory = CheckoutApi) -> None:
        self._checkout_api_factory = checkout_api_factory

    def fragment_context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        lines = posted_shop_cart(theme_request.query_args.get(CART_FIELD))
        if not lines:
            return {"state": "empty"}
        default_currency = self._checkout_api_factory(theme_request).default_currency()
        views = [
            _line_view(line, line.get("currency") or default_currency) for line in lines
        ]
        net_total = sum(
            line_amounts(line)[0] * int(line.get("quantity") or 1) for line in lines
        )
        gross_total = sum(
            line_amounts(line)[1] * int(line.get("quantity") or 1) for line in lines
        )
        return {
            "state": "items",
            "lines": views,
            "item_count": sum(int(line.get("quantity") or 0) for line in lines),
            "subtotal": price_display_view(
                net_total, gross_total, lines[0].get("currency") or default_currency
            ),
        }
