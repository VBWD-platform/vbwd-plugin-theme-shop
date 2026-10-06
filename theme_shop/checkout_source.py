"""The "shop" checkout source — the twin of fe-user ``shop/checkoutSource.ts`` (S152-08).

``?source=shop`` checks out the shop cart (``vbwd_shop_cart``, posted by the
checkout island): one line per item at ``price × quantity``, a coupon in the
``ECOMMERCE`` scope on the cart subtotal, and ``POST /api/v1/shop/cart/checkout``
with the items, the payment method and the applied coupon. The answer becomes
the PENDING invoice the post-submit dispatch routes; the runtime empties the
shop cart on the redirect, as the SPA's ``cart.clearCart()``.
"""
from decimal import Decimal
from typing import Any, Callable, Dict, List, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.checkout_api import CheckoutApi
from plugins.theme_checkout.theme_checkout.checkout_sources import (
    CheckoutRouteContext,
    CheckoutSource,
    CheckoutSummary,
)
from plugins.theme_checkout.theme_checkout.coupon import price_coupon
from plugins.theme_checkout.theme_checkout.price_display import price_display_view

from .cart import line_amounts
from .shop_api import ShopApi

SHOP_SOURCE_ID = "shop"
SHOP_CART_KEY = "vbwd_shop_cart"
SUMMARY_TEMPLATE = "shop/checkout_summary.html.j2"
COUPON_SCOPE = "ECOMMERCE"
CART_IS_EMPTY = "Cart is empty"
PENDING_STATUS = "PENDING"
BAD_REQUEST = 400
ZERO = Decimal("0")

ApiFactory = Callable[[ThemeRequest], Any]
CartLine = Mapping[str, Any]


def matches_shop(context: CheckoutRouteContext) -> bool:
    return context.source == SHOP_SOURCE_ID


def _quantity(line: CartLine) -> int:
    return int(line.get("quantity") or 1)


def _summary_row(line: CartLine, currency: str) -> Dict[str, Any]:
    """``ShopCheckoutSummary``'s row: name, ``x<quantity>`` when > 1, the line price."""
    net, gross = line_amounts(line)
    quantity = _quantity(line)
    return {
        "product_id": line.get("productId") or "",
        "name": line.get("productName") or "",
        "quantity": quantity,
        "price": price_display_view(
            net * quantity,
            gross * quantity,
            currency,
            line.get("effectiveDisplayMode"),
            line.get("pricesDisplayMode"),
        ),
    }


class ShopCheckout:
    """Prices and submits the shop cart of one checkout request."""

    def __init__(
        self,
        api_factory: ApiFactory = ShopApi,
        checkout_api_factory: ApiFactory = CheckoutApi,
    ) -> None:
        self._api_factory = api_factory
        self._checkout_api_factory = checkout_api_factory

    def checkout_source(self) -> CheckoutSource:
        return CheckoutSource(
            id=SHOP_SOURCE_ID,
            matches=matches_shop,
            load_summary=self.load_summary,
            submit=self.submit,
            summary_template=SUMMARY_TEMPLATE,
            cart_key=SHOP_CART_KEY,
        )

    def load_summary(
        self, theme_request: ThemeRequest, context: CheckoutRouteContext
    ) -> CheckoutSummary:
        lines: List[CartLine] = list(context.cart_items)
        if not lines:
            raise ThemeApiError(BAD_REQUEST, CART_IS_EMPTY)
        checkout_api = self._checkout_api_factory(theme_request)
        default_currency = checkout_api.default_currency()
        subtotal = sum(
            (Decimal(str(line.get("price") or 0)) * _quantity(line) for line in lines),
            ZERO,
        )
        coupon = price_coupon(checkout_api, context.coupon_code, subtotal, COUPON_SCOPE)
        return CheckoutSummary(
            line_items=tuple(
                {
                    "type": "shop_product",
                    "id": line.get("productId"),
                    "name": line.get("productName"),
                    "price": float(line.get("price") or 0) * _quantity(line),
                    "quantity": _quantity(line),
                    "currency": line.get("currency") or default_currency,
                }
                for line in lines
            ),
            order_total=max(ZERO, subtotal - coupon.discount_amount),
            currency=lines[0].get("currency") or default_currency,
            discount_amount=coupon.discount_amount,
            applied_coupon_code=coupon.applied_code,
            coupon_error=coupon.error,
            template_context={
                "rows": [
                    _summary_row(line, line.get("currency") or default_currency)
                    for line in lines
                ]
            },
        )

    def submit(
        self,
        theme_request: ThemeRequest,
        context: CheckoutRouteContext,
        payment_method_code: Optional[str],
    ) -> Mapping[str, Any]:
        payload: Dict[str, Any] = {
            "items": [
                {
                    "product_id": line.get("productId"),
                    "quantity": _quantity(line),
                    "variant_id": line.get("variantId") or None,
                }
                for line in context.cart_items
            ]
        }
        if payment_method_code:
            payload["payment_method_code"] = payment_method_code
        if context.coupon_code:
            payload["coupon_code"] = context.coupon_code
        response = self._api_factory(theme_request).cart_checkout(payload)
        return {
            "invoice": {
                "id": response.get("invoice_id"),
                "invoice_number": response.get("invoice_number"),
                "status": PENDING_STATUS,
                "amount": response.get("total"),
                "total_amount": response.get("total"),
            }
        }
