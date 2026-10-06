"""The ProductGrid CMS component — the twin of ``ProductCatalog.vue`` (S152-08).

Facets come from ``GET /api/v1/shop/filters`` and each ``options_endpoint``;
products from ``GET /api/v1/shop/products`` with the SPA's query. The toolbar
and filter bar are one GET form: it works without JavaScript (the page
re-renders from the query) and htmx swaps the whole catalogue from
``/_render/_fragment/shop/products`` (the search input keeps focus by its id).
A chip submits ``toggle_tag`` (the current tags with that tag toggled), a pager
button its ``page``; any other change starts again at page 1.
"""
from typing import Any, Callable, Dict, List, Mapping, Optional

from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_checkout.theme_checkout.price_display import price_display_view
from plugins.theme_cms.theme_cms.components.catalogue_filters import load_facets

from .nullish import present_or
from .shop_api import ShopApi

DEFAULT_PER_PAGE = 12
DEFAULT_SORT = "newest"
SORT_OPTIONS = (
    ("newest", "shop.catalog.sortNewest"),
    ("name_asc", "shop.catalog.sortNameAsc"),
    ("name_desc", "shop.catalog.sortNameDesc"),
    ("price_asc", "shop.catalog.sortPriceAsc"),
    ("price_desc", "shop.catalog.sortPriceDesc"),
)
LOAD_FAILED_KEY = "shop.catalog.loadFailed"
CATEGORY_FACET = "category"
TAGS_FACET = "tags"
TAG_SEPARATOR = ","
FIRST_PAGE = 1
CATALOG_PATH_FIELD = "catalog_path"
DEFAULT_CATALOG_PATH = "/shop"

ApiFactory = Callable[[ThemeRequest], Any]


def _page_number(raw_page: Any) -> int:
    try:
        return max(int(raw_page), FIRST_PAGE)
    except (TypeError, ValueError):
        return FIRST_PAGE


def _toggled(tags: List[str], tag: str) -> List[str]:
    return (
        [current for current in tags if current != tag] if tag in tags else tags + [tag]
    )


def catalog_filters(
    query_args: Mapping[str, Any], route_category: Optional[str]
) -> Dict[str, Any]:
    """The catalogue state the form / URL carries (``useCatalogueFilters``)."""
    tags = [
        tag for tag in (query_args.get(TAGS_FACET) or "").split(TAG_SEPARATOR) if tag
    ]
    toggle_tag = query_args.get("toggle_tag")
    if toggle_tag:
        tags = _toggled(tags, toggle_tag)
    category = (
        query_args.get(CATEGORY_FACET)
        if CATEGORY_FACET in query_args
        else route_category
    )
    is_filter_change = bool(toggle_tag)
    return {
        "q": (query_args.get("q") or "").strip(),
        "sort": query_args.get("sort") or DEFAULT_SORT,
        "category": category or "",
        "tags": tags,
        "page": FIRST_PAGE
        if is_filter_change
        else _page_number(query_args.get("page")),
    }


def _products_query(filters: Mapping[str, Any]) -> Dict[str, Any]:
    """``buildProductsUrl`` — empty values are left out."""
    query: Dict[str, Any] = {"page": filters["page"], "per_page": DEFAULT_PER_PAGE}
    if filters["q"]:
        query["q"] = filters["q"]
    if filters["tags"]:
        query["tags"] = TAG_SEPARATOR.join(filters["tags"])
    if filters["category"]:
        query[CATEGORY_FACET] = filters["category"]
    query["sort"] = filters["sort"]
    return query


def _card(
    product: Mapping[str, Any], tag_labels: Mapping[str, str], active_tags: List[str]
) -> Dict[str, Any]:
    pricing = product.get("pricing") or {}
    price = product.get("price")
    return {
        "slug": product.get("slug") or "",
        "name": product.get("name") or "",
        "href": f"/shop/product/{product.get('slug')}",
        "image_url": product.get("primary_image_url"),
        "price": price_display_view(
            present_or(pricing.get("net_amount"), price),
            present_or(pricing.get("gross_amount"), price),
            product.get("currency"),
            pricing.get("effective_display_mode"),
            pricing.get("prices_display_mode"),
        ),
        "tags": [
            {
                "slug": tag,
                "label": tag_labels.get(tag, tag),
                "active": tag in active_tags,
            }
            for tag in product.get("tags") or []
        ],
    }


def _pager(current_page: int, total_pages: int) -> Optional[Dict[str, Any]]:
    if total_pages <= FIRST_PAGE:
        return None
    return {
        "current": current_page,
        "total": total_pages,
        "previous": current_page - 1 if current_page > FIRST_PAGE else None,
        "next": current_page + 1 if current_page < total_pages else None,
    }


class ProductGrid:
    """``build_context`` (the component) and the catalogue fragment's context."""

    def __init__(self, api_factory: ApiFactory = ShopApi) -> None:
        self._api_factory = api_factory

    def build_context(
        self,
        widget_config: Mapping[str, Any],
        page: Mapping[str, Any],
        route_params: Mapping[str, Any],
        theme_request: ThemeRequest,
    ) -> Dict[str, Any]:
        filters = catalog_filters(theme_request.query_args, route_params.get("slug"))
        return self._catalog(theme_request, filters, theme_request.path)

    def fragment_context(self, theme_request: ThemeRequest) -> Dict[str, Any]:
        query_args = theme_request.query_args
        catalog_path = query_args.get(CATALOG_PATH_FIELD) or DEFAULT_CATALOG_PATH
        filters = catalog_filters(query_args, None)
        return {
            "component_context": self._catalog(theme_request, filters, catalog_path)
        }

    def _catalog(
        self, theme_request: ThemeRequest, filters: Dict[str, Any], form_action: str
    ) -> Dict[str, Any]:
        api = self._api_factory(theme_request)
        facets = load_facets(api)
        context: Dict[str, Any] = {
            "form_action": form_action,
            "filters": filters,
            "facets": facets,
            "sort_options": SORT_OPTIONS,
        }
        try:
            listing = api.products(_products_query(filters))
        except ThemeApiError as load_error:
            return {**context, "state": "error", "error": load_error.message or None}
        tag_facet = next(
            (facet for facet in facets if facet.get("key") == TAGS_FACET), {}
        )
        tag_labels = {
            option["value"]: option["label"]
            for option in tag_facet.get("options") or []
        }
        cards = [
            _card(product, tag_labels, filters["tags"])
            for product in listing.get("items") or []
        ]
        return {
            **context,
            "state": "products" if cards else "empty",
            "products": cards,
            "pager": _pager(filters["page"], int(listing.get("pages") or FIRST_PAGE)),
        }
