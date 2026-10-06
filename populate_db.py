"""Demo data for theme_shop: nothing to seed.

The plugin owns no tables (S152 D9); its only state is its config. Kept so the
"install all plugins" recipes treat every plugin uniformly.
"""


def populate_db() -> None:
    """No-op: theme_shop has no data to seed."""


if __name__ == "__main__":
    populate_db()
