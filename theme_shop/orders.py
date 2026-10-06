"""``/shop/orders`` and ``/shop/orders/<id>`` — ``OrderHistory.vue`` / ``OrderDetail.vue``.

Auth-only pages (D4/D7): the anonymous page render knows nobody, so the order
data is a personalised region that shows the loading state until the runtime
re-renders it with the buyer's bearer. Then ``GET /api/v1/shop/orders[/<id>]``
answers with the API's own owner scoping: another user's order (403), an
unknown one (404) and a malformed id are all the SPA's "Order not found." — no
other user's data ever reaches the page. (The SPA's OrderDetail never fetches,
so it always shows that message; the themed page shows the buyer's order.)
"""
import uuid
from datetime import datetime
from typing import Any, Callable, Dict, Mapping, Optional, Tuple

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_cms.theme_cms.components.pricing import format_money

from .shop_api import ShopApi

LOAD_ORDERS_FAILED_KEY = "shop.orders.loadFailed"
NOT_FOUND_STATUSES = (400, 403, 404)
SHORT_MONTHS = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)
LONG_MONTHS = (
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
)

ApiFactory = Callable[[ThemeRequest], Any]


def _local_date(raw: Optional[str], months: Tuple[str, ...]) -> str:
    """``toLocaleDateString`` in en-US: ``Oct 4, 2026`` / ``October 4, 2026``."""
    if not raw:
        return ""
    try:
        moment = datetime.fromisoformat(raw)
    except ValueError:
        return raw
    return f"{months[moment.month - 1]} {moment.day}, {moment.year}"


def _is_order_id(order_id: str) -> bool:
    try:
        uuid.UUID(order_id)
    except ValueError:
        return False
    return True


def _order_row(order: Mapping[str, Any]) -> Dict[str, Any]:
    return {
        "href": f"/shop/orders/{order.get('id')}",
        "number": order.get("order_number") or "",
        "status": order.get("status") or "",
        "total": format_money(order.get("total_amount"), order.get("currency")),
        "date": _local_date(order.get("created_at"), SHORT_MONTHS),
    }


def _order_view(order: Mapping[str, Any]) -> Dict[str, Any]:
    currency = order.get("currency")
    tracking_number = order.get("tracking_number")
    return {
        "number": order.get("order_number") or "",
        "status": order.get("status") or "",
        "tracking": (
            {"carrier": order.get("shipping_method") or "", "number": tracking_number}
            if tracking_number
            else None
        ),
        "items": [
            {
                "name": (item.get("product_snapshot") or {}).get("name") or "",
                "quantity": item.get("quantity"),
                "price": format_money(
                    float(item.get("unit_price") or 0) * int(item.get("quantity") or 1),
                    currency,
                ),
            }
            for item in order.get("items") or []
        ],
        "total": format_money(order.get("total_amount"), currency),
        "placed_on": _local_date(order.get("created_at"), LONG_MONTHS),
    }


class OrderHistoryPage:
    """The ``/shop/orders`` page context."""

    def __init__(self, api_factory: ApiFactory = ShopApi) -> None:
        self._api_factory = api_factory

    def context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        if theme_request.viewer.user_id is None:
            return {"page_title": "", "orders_state": "loading"}
        try:
            orders = self._api_factory(theme_request).orders().get("orders") or []
        except ThemeApiError as load_error:
            return {
                "page_title": "",
                "orders_state": "error",
                "error": load_error.message or None,
            }
        return {
            "page_title": "",
            "orders_state": "orders" if orders else "empty",
            "orders": [_order_row(order) for order in orders],
        }


class OrderDetailPage:
    """The ``/shop/orders/<order_id>`` page context."""

    def __init__(self, api_factory: ApiFactory = ShopApi) -> None:
        self._api_factory = api_factory

    def context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        order_id = str(theme_request.view_args.get("order_id") or "")
        if theme_request.viewer.user_id is None:
            return {"page_title": "", "order_state": "loading"}
        if not _is_order_id(order_id):
            return {"page_title": "", "order_state": "not_found"}
        try:
            order = self._api_factory(theme_request).order(order_id)["order"]
        except ThemeApiError as load_error:
            if load_error.status in NOT_FOUND_STATUSES:
                return {"page_title": "", "order_state": "not_found"}
            return {
                "page_title": "",
                "order_state": "error",
                "error": load_error.message,
            }
        return {"page_title": "", "order_state": "order", "order": _order_view(order)}
