"""S152-08 — the ProductGrid CMS component, the twin of ``ProductCatalog.vue``.

* facets from ``GET /api/v1/shop/filters``, options from each
  ``options_endpoint`` (first array of the answer; ``value ?? slug`` /
  ``label ?? name ?? value ?? slug``);
* products from ``GET /api/v1/shop/products`` with the SPA's query
  (``page``, ``per_page`` 12, ``q``, ``tags`` comma-joined, facets, ``sort``);
* on ``/shop/category/<slug>`` the category facet starts at the route slug;
* a chip submits ``toggle_tag`` (the current tags toggled), a pager button its
  ``page``; any other change resets to page 1 (``useCatalogueFilters``).
"""
from plugins.theme.theme.theme_api import ThemeApiError
from plugins.theme_checkout.tests.unit.fakes import FakeThemeRequest
from plugins.theme_shop.tests.unit.fakes import FakeShopApi
from plugins.theme_shop.theme_shop.catalog import ProductGrid


def _grid(query=None, route_params=None, api=None, path="/shop"):
    api = api or FakeShopApi()
    context = ProductGrid(api.factory).build_context(
        {}, {}, route_params or {}, FakeThemeRequest(query or {}, path=path)
    )
    return context, api


def _products_query(api):
    return next(call[1] for call in api.calls if call[0] == "products")


def test_the_default_query_is_page_one_twelve_newest():
    context, api = _grid()

    assert _products_query(api) == {"page": 1, "per_page": 12, "sort": "newest"}
    assert context["state"] == "products"
    assert context["form_action"] == "/shop"


def test_search_tags_category_sort_and_page_reach_the_api():
    context, api = _grid(
        {
            "q": "head",
            "tags": "wireless,usb",
            "category": "audio",
            "sort": "price_asc",
            "page": "2",
        }
    )

    assert _products_query(api) == {
        "page": 2,
        "per_page": 12,
        "q": "head",
        "tags": "wireless,usb",
        "category": "audio",
        "sort": "price_asc",
    }
    assert context["filters"]["tags"] == ["wireless", "usb"]


def test_the_category_route_seeds_the_category_facet():
    context, api = _grid(route_params={"slug": "audio"}, path="/shop/category/audio")

    assert _products_query(api)["category"] == "audio"
    assert context["filters"]["category"] == "audio"


def test_an_explicit_empty_category_overrides_the_route():
    _context, api = _grid({"category": ""}, route_params={"slug": "audio"})

    assert "category" not in _products_query(api)


def test_a_chip_toggles_its_tag_and_resets_the_page():
    added, add_api = _grid({"tags": "wireless", "toggle_tag": "usb", "page": "3"})
    removed, remove_api = _grid({"tags": "wireless,usb", "toggle_tag": "wireless"})

    assert _products_query(add_api)["tags"] == "wireless,usb"
    assert _products_query(add_api)["page"] == 1
    assert "tags" not in _products_query(_grid({"tags": "usb", "toggle_tag": "usb"})[1])
    assert _products_query(remove_api)["tags"] == "usb"


def test_facets_and_options_are_resolved_through_the_descriptor():
    context, api = _grid()

    assert [facet["key"] for facet in context["facets"]] == ["category", "tags"]
    assert context["facets"][0]["options"] == [{"value": "audio", "label": "Audio"}]
    assert ("options", "/api/v1/shop/categories") in api.calls


def test_a_card_has_its_link_price_and_labelled_tags():
    context, _api = _grid({"tags": "wireless"})

    card = context["products"][0]
    assert card["href"] == "/shop/product/wireless-headphones-pro"
    assert card["price"].label == "€99.00"
    assert card["tags"] == [{"slug": "wireless", "label": "Wireless", "active": True}]


def test_states_error_empty_and_pager():
    failed, _api = _grid(api=FakeShopApi(products=ThemeApiError(500, "boom")))
    empty, _api = _grid(api=FakeShopApi(products={"items": [], "pages": 1}))
    paged, _api = _grid(
        {"page": "2"}, api=FakeShopApi(products={"items": [], "pages": 3})
    )

    assert failed["state"] == "error" and failed["error"] == "boom"
    assert empty["state"] == "empty"
    assert paged["pager"] == {"current": 2, "total": 3, "previous": 1, "next": 3}


def test_a_missing_filters_endpoint_still_lists_products():
    context, _api = _grid(api=FakeShopApi(filters=ThemeApiError(404, "x")))

    assert context["facets"] == []
    assert context["state"] == "products"


def test_the_fragment_uses_the_posted_page_path_as_the_form_action():
    api = FakeShopApi()

    context = ProductGrid(api.factory).fragment_context(
        FakeThemeRequest(
            {"catalog_path": "/shop/category/audio", "category": "audio"},
            path="/_render/_fragment/shop/products",
        )
    )

    assert context["component_context"]["form_action"] == "/shop/category/audio"
    assert _products_query(api)["category"] == "audio"
