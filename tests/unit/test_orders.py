"""S152-08 — ``/shop/orders`` and ``/shop/orders/<id>`` (auth-only, D4/D7).

The anonymous page render knows nobody: its region shows the loading state.
When the runtime re-renders the region with the buyer's bearer,
``GET /api/v1/shop/orders[/<id>]`` answers with the API's own owner scoping;
another user's order (403), an unknown one (404) or a malformed id all show the
same "Order not found." as the SPA, and no data of the other user.
"""
from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_checkout.tests.unit.fakes import FakeThemeRequest
from plugins.theme_shop.tests.unit.fakes import ORDER, FakeShopApi
from plugins.theme_shop.theme_shop.orders import OrderDetailPage, OrderHistoryPage

ORDER_ID = ORDER["id"]


def _history(user_id=None, api=None):
    api = api or FakeShopApi()
    return OrderHistoryPage(api.factory).context(FakeThemeRequest(user_id=user_id)), api


def _detail(order_id=ORDER_ID, user_id="user-a", api=None):
    api = api or FakeShopApi()
    context = OrderDetailPage(api.factory).context(
        FakeThemeRequest(view_args={"order_id": order_id}, user_id=user_id)
    )
    return context, api


def test_the_anonymous_history_is_loading_and_asks_nothing():
    context, api = _history()

    assert context["orders_state"] == "loading"
    assert api.calls == []


def test_the_viewer_history_lists_the_orders():
    context, _api = _history(user_id="user-a")

    assert context["orders_state"] == "orders"
    row = context["orders"][0]
    assert row["href"] == f"/shop/orders/{ORDER_ID}"
    assert row["number"] == "ORD-1" and row["status"] == "pending"
    assert row["total"] == "€99.00"
    assert row["date"] == "Oct 4, 2026"


def test_history_empty_and_error_states():
    empty, _api = _history("u", FakeShopApi(orders={"orders": []}))
    failed, _api = _history("u", FakeShopApi(orders=ThemeApiError(500, "boom")))

    assert empty["orders_state"] == "empty"
    assert failed["orders_state"] == "error" and failed["error"] == "boom"


def test_the_viewer_detail_shows_the_order():
    context, api = _detail()

    assert api.calls == [("order", ORDER_ID)]
    assert context["order_state"] == "order"
    order = context["order"]
    assert order["number"] == "ORD-1"
    assert order["items"][0] == {"name": "Cable", "quantity": 2, "price": "€99.00"}
    assert order["total"] == "€99.00"
    assert order["placed_on"] == "October 4, 2026"
    assert order["tracking"] is None


def test_another_users_or_an_unknown_order_is_not_found():
    for refusal in (
        ThemeApiError(403, "Forbidden"),
        ThemeApiError(404, "Order not found"),
    ):
        context, _api = _detail(api=FakeShopApi(order=refusal))

        assert context["order_state"] == "not_found"
        assert "order" not in context


def test_a_malformed_id_is_not_found_without_asking():
    context, api = _detail(order_id="not-a-uuid")

    assert context["order_state"] == "not_found"
    assert api.calls == []


def test_the_anonymous_detail_is_loading():
    context, api = _detail(user_id=None)

    assert context["order_state"] == "loading"
    assert api.calls == []


def test_tracking_is_shown_when_the_order_has_a_tracking_number():
    shipped = {**ORDER, "tracking_number": "TRK-9", "shipping_method": "DHL"}

    context, _api = _detail(api=FakeShopApi(order={"order": shipped}))

    assert context["order"]["tracking"] == {"carrier": "DHL", "number": "TRK-9"}
