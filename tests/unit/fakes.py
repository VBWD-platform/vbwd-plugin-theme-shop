"""Test doubles for the theme_shop unit tests: a scripted ``ShopApi`` + payloads."""
from plugins.theme.theme.theme_api import ThemeApiError

FACETS = {
    "facets": [
        {
            "key": "category",
            "label": "Category",
            "control": "select",
            "options_endpoint": "/api/v1/shop/categories",
        },
        {
            "key": "tags",
            "label": "Tags",
            "control": "chips",
            "multi": True,
            "options_endpoint": "/api/v1/shop/tags",
        },
    ]
}
CATEGORIES = {"categories": [{"slug": "audio", "name": "Audio"}]}
TAGS = {"tags": [{"slug": "wireless", "name": "Wireless"}]}
PRODUCT_CARD = {
    "id": "p-1",
    "slug": "wireless-headphones-pro",
    "name": "Wireless Headphones Pro",
    "price": 99.0,
    "primary_image_url": "/uploads/h.png",
    "tags": ["wireless"],
    "pricing": {
        "net_amount": "83.19",
        "gross_amount": "99.00",
        "effective_display_mode": "brutto",
        "prices_display_mode": "brutto",
    },
}
PRODUCT = {
    **PRODUCT_CARD,
    "description": "Noise cancelling",
    "weight": "0.3",
    "has_variants": False,
    "variants": [],
    "images": [
        {"id": "i-1", "url": "/uploads/h.png", "alt": "front"},
        {"id": "i-2", "url": "/uploads/h2.png", "alt": ""},
    ],
    "stock_available": 5,
    "product_type_slug": None,
    "type_field_values": {},
    "pricing": {
        **PRODUCT_CARD["pricing"],
        "taxes": [{"code": "VAT", "rate": "19", "amount": "15.81"}],
    },
}
ORDER = {
    "id": "11111111-1111-1111-1111-111111111111",
    "order_number": "ORD-1",
    "status": "pending",
    "total_amount": "99.00",
    "tracking_number": None,
    "shipping_method": None,
    "created_at": "2026-10-04T09:30:00",
    "items": [
        {
            "id": "oi-1",
            "quantity": 2,
            "unit_price": "49.50",
            "product_snapshot": {"name": "Cable"},
        }
    ],
}


class FakeShopApi:
    """Same methods as ``ShopApi``; answers by method name (exceptions are raised)."""

    def __init__(self, **answers):
        self.answers = {
            "filters": FACETS,
            "options": {
                "/api/v1/shop/categories": CATEGORIES,
                "/api/v1/shop/tags": TAGS,
            },
            "products": {
                "items": [PRODUCT_CARD],
                "total": 1,
                "page": 1,
                "per_page": 12,
                "pages": 1,
            },
            "product": {"product": PRODUCT},
            "orders": {"orders": [ORDER], "total": 1},
            "order": {"order": ORDER},
            "cart_checkout": {
                "invoice_id": "inv-7",
                "invoice_number": "SH-1",
                "total": "99.00",
            },
            **answers,
        }
        self.calls = []

    def factory(self, theme_request):
        self.theme_request = theme_request
        return self

    def _answer(self, name, *arguments):
        self.calls.append((name,) + arguments)
        answer = self.answers.get(name)
        if isinstance(answer, Exception):
            raise answer
        if answer is None:
            raise ThemeApiError(404, "Not found")
        return answer

    def filters(self):
        return self._answer("filters")

    def options(self, endpoint):
        self.calls.append(("options", endpoint))
        answer = self.answers["options"].get(endpoint)
        if isinstance(answer, Exception) or answer is None:
            raise answer or ThemeApiError(404, "Not found")
        return answer

    def products(self, query):
        return self._answer("products", dict(query))

    def product(self, slug):
        return self._answer("product", slug)

    def product_type(self, slug):
        return self._answer("product_type", slug)

    def orders(self):
        return self._answer("orders")

    def order(self, order_id):
        return self._answer("order", order_id)

    def cart_checkout(self, payload):
        return self._answer("cart_checkout", payload)
