"""Where theme_shop's contributed templates, translations and stylesheets live."""
from pathlib import Path

PACKAGE_DIRECTORY = Path(__file__).resolve().parent
TEMPLATES_DIRECTORY = PACKAGE_DIRECTORY / "templates"
TRANSLATIONS_DIRECTORY = PACKAGE_DIRECTORY / "translations"
# ``public/`` CSS: the SPA component CSS, structural only (S152-06c rules).
STYLESHEETS_DIRECTORY = PACKAGE_DIRECTORY / "stylesheets"
