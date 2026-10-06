"""Integration fixtures: a real ``create_app`` in theme mode with the shop stack.

Boot: email, cms, checkout, shop (the REAL domain plugins and their public API),
theme, theme_cms, theme_checkout, theme_shop; fe-user "cms", "checkout" and
"shop" enabled. Data lives in the shared ``*_test`` database, each test in a
rolled-back transaction; products, categories, payment methods and CMS pages are
seeded through the admin HTTP APIs.
"""
import pytest

from plugins.theme_checkout.tests.integration.themed_stack import (
    ADMIN_USER,
    TEST_USER,
    bearer_of,
    rolled_back_test_data,
    themed_app,
)

BOOT_ORDER = (
    "email",
    "cms",
    "checkout",
    "shop",
    "theme",
    "theme_cms",
    "theme_checkout",
    "theme_shop",
)
FE_USER_PLUGINS = ("cms", "checkout", "shop")


@pytest.fixture(scope="module")
def app(tmp_path_factory):
    var_directory = tmp_path_factory.mktemp("theme-shop-var")
    with themed_app(var_directory, BOOT_ORDER, FE_USER_PLUGINS) as application:
        yield application


@pytest.fixture
def db(app):
    with rolled_back_test_data(app) as database:
        yield database


@pytest.fixture
def client(app, db):
    return app.test_client()


@pytest.fixture
def bearer(client):
    return bearer_of(client, TEST_USER)


@pytest.fixture
def admin_headers(client):
    return bearer_of(client, ADMIN_USER)


@pytest.fixture
def cms(client):
    from plugins.theme_cms.tests.integration.cms_seed import CmsAdminSeeder

    return CmsAdminSeeder(client)
