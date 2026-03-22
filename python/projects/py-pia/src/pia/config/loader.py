"""Product configuration loader from YAML files."""

import structlog
import yaml
from pathlib import Path

from pia.config.settings import get_settings
from pia.models.product import Product

log = structlog.get_logger()


def load_product(path: Path) -> Product:
    """Load a product from a YAML config file.

    Args:
        path: Path to the YAML configuration file.

    Returns:
        A validated Product instance.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValidationError: If the YAML content does not match the Product schema.
    """
    with open(path) as f:
        data = yaml.safe_load(f)
    product = Product.model_validate(data)
    product.config_path = str(path)
    return product


def load_all_products() -> list[Product]:
    """Load all product configs from the configured products directory.

    Returns:
        List of Product instances. Products that fail to load are skipped
        with a warning log.
    """
    settings = get_settings()
    products: list[Product] = []
    for yaml_file in sorted(settings.products_dir.glob("*.yaml")):
        try:
            products.append(load_product(yaml_file))
        except Exception as e:
            log.warning(
                "failed to load product config",
                path=str(yaml_file),
                error=str(e),
            )
    return products
