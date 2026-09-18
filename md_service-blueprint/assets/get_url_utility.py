"""
Runtime URL resolver for deployed Lambdas.
Location: src/deployed_utilities_references/get_url_utility.py

At deploy time the environment-specific URL file
(configuration/urls.beta.yaml / configuration/urls.prod.yaml) is copied into this
package as `urls.yaml` and shipped inside the Lambda zip.
Application code calls get_url(key) to resolve outbound service URLs from that
packaged file only — no hardcoded URLs and no per-URL Lambda environment variables.
"""
import logging
import os

import yaml

logger = logging.getLogger()

_URLS_FILE_NAME = "urls.yaml"
_URLS_FILE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), _URLS_FILE_NAME)

_url_map = None


class UrlConfigurationError(RuntimeError):
    """Raised when a required service URL key is missing from packaged urls.yaml."""


def _load_url_map():
    """Load and cache urls.yaml."""
    global _url_map
    if _url_map is not None:
        return _url_map
    try:
        with open(_URLS_FILE_PATH, "r", encoding="utf-8") as urls_file:
            _url_map = yaml.safe_load(urls_file) or {}
    except FileNotFoundError as exc:
        raise UrlConfigurationError(
            f"{_URLS_FILE_NAME} not found at {_URLS_FILE_PATH}. "
            "Deploy must package configuration/urls.{beta,prod}.yaml into the Lambda zip."
        ) from exc
    except Exception as exc:
        raise UrlConfigurationError(
            f"Could not load {_URLS_FILE_NAME} from {_URLS_FILE_PATH}: {exc}"
        ) from exc
    return _url_map


def reset_url_map_cache() -> None:
    """Clear cached urls.yaml (for tests)."""
    global _url_map
    _url_map = None


def get_url(key: str) -> str:
    """
    Resolve a service URL by key from packaged urls.yaml.
    Raises UrlConfigurationError when the key is missing or empty.
    """
    url_map = _load_url_map()
    value = url_map.get(key)
    if value is None or not str(value).strip():
        raise UrlConfigurationError(
            f"URL key '{key}' is missing or empty in {_URLS_FILE_NAME}. "
            f"Add it to configuration/urls.{{beta,prod}}.yaml."
        )
    return str(value).strip()


def get_environment() -> str:
    """
    Current deployment stage (beta, prod, ...), read from the ENVIRONMENT env var.

    ENVIRONMENT is injected into the Lambda by Terraform (infra/terraform/main.tf).
    This intentionally does NOT default: a missing ENVIRONMENT must fail loudly rather
    than silently building beta-stage URLs on a prod Lambda (or vice versa).
    """
    environment = os.getenv("ENVIRONMENT")
    if not environment or not environment.strip():
        raise UrlConfigurationError(
            "ENVIRONMENT is not set. It must be provided as a Lambda environment "
            "variable (wired via infra/terraform/main.tf); it is not read from urls.yaml."
        )
    return environment.strip()
