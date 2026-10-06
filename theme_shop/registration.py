"""What theme_shop puts into the theme platform (owner fe-user ``shop``).

fe-user mounts ``/shop``, ``/shop/category/:slug``, ``/shop/product/:slug`` and
``/shop/cart`` as ``CmsPage`` with fixed slugs (``shop``, ``shop-product-detail``,
``shop-cart``): each themed route renders that CMS page through theme_cms's
pipeline with the route params in context (S152-06 §7). The order pages are
auth-only theme pages; the catalogue and cart islands are fragments.
"""
from typing import Any, Callable, Dict, List

from plugins.theme.theme.fragment_registry import ThemeFragment
from plugins.theme.theme.page_registry import PUBLIC_PAGE, USER_PAGE, ThemePage
from plugins.theme.theme.theme_request import ThemeRequest
from plugins.theme_cms.theme_cms.pages import DISPATCH_TEMPLATE
from plugins.theme_cms.theme_cms.registries import ComponentTemplate

from .cart import ShoppingCart
from .catalog import ProductGrid
from .orders import OrderDetailPage, OrderHistoryPage
from .product_detail import ProductDetail

SHOP_FE_USER_PLUGIN = "shop"
SHOP_PAGE_PRIORITY = 50
FRAGMENT_PREFIX = "/_render/_fragment/shop"
CMS_PAGE_ROUTES = (
    ("/shop", "shop_catalog", "shop"),
    ("/shop/category/<slug>", "shop_category", "shop"),
    ("/shop/product/<slug>", "shop_product", "shop-product-detail"),
    ("/shop/cart", "shop_cart", "shop-cart"),
)


def _page(
    rule: str, endpoint: str, template: str, build_context, auth: str = PUBLIC_PAGE
) -> ThemePage:
    return ThemePage(
        rule=rule,
        endpoint=endpoint,
        owner_fe_user_plugin=SHOP_FE_USER_PLUGIN,
        priority=SHOP_PAGE_PRIORITY,
        auth=auth,
        template=template,
        build_context=build_context,
    )


def _cms_page_context(
    cms_pages: Any, cms_slug: str
) -> Callable[[ThemeRequest], Dict[str, Any]]:
    def build_context(theme_request: ThemeRequest) -> Dict[str, Any]:
        page_context: Dict[str, Any] = cms_pages.cms_slug_page_context(
            theme_request, cms_slug
        )
        return page_context

    return build_context


def shop_pages(cms_pages: Any) -> List[ThemePage]:
    pages = [
        _page(rule, endpoint, DISPATCH_TEMPLATE, _cms_page_context(cms_pages, cms_slug))
        for rule, endpoint, cms_slug in CMS_PAGE_ROUTES
    ]
    pages.append(
        _page(
            "/shop/orders",
            "shop_orders",
            "shop/orders.html.j2",
            OrderHistoryPage().context,
            USER_PAGE,
        )
    )
    pages.append(
        _page(
            "/shop/orders/<order_id>",
            "shop_order_detail",
            "shop/order_detail.html.j2",
            OrderDetailPage().context,
            USER_PAGE,
        )
    )
    return pages


def shop_fragments(product_grid: ProductGrid) -> List[ThemeFragment]:
    return [
        ThemeFragment(
            rule=f"{FRAGMENT_PREFIX}/products",
            endpoint="shop_products_fragment",
            owner_fe_user_plugin=SHOP_FE_USER_PLUGIN,
            template="shop/_products_fragment.html.j2",
            build_context=product_grid.fragment_context,
        ),
        ThemeFragment(
            rule=f"{FRAGMENT_PREFIX}/cart",
            endpoint="shop_cart_fragment",
            owner_fe_user_plugin=SHOP_FE_USER_PLUGIN,
            template="shop/_cart_fragment.html.j2",
            build_context=ShoppingCart().fragment_context,
            methods=("POST",),
        ),
    ]


def _no_context(widget_config, page, route_params, theme_request) -> Dict[str, Any]:
    """ShoppingCart / CartBadge: the browser cart is only known client-side."""
    return {}


def shop_components(product_grid: ProductGrid) -> List[ComponentTemplate]:
    """The twins of fe-user ``registerCmsVueComponent`` (same names)."""
    return [
        ComponentTemplate(
            "ProductGrid",
            "shop/components/product_grid.html.j2",
            product_grid.build_context,
        ),
        ComponentTemplate(
            "ProductDetail",
            "shop/components/product_detail.html.j2",
            ProductDetail().build_context,
        ),
        ComponentTemplate(
            "ShoppingCart", "shop/components/shopping_cart.html.j2", _no_context
        ),
        ComponentTemplate(
            "CartBadge", "shop/components/cart_badge.html.j2", _no_context
        ),
    ]
