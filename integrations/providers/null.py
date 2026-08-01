import logging
from integrations.base import ProductAPIClient, ProductDTO

logger = logging.getLogger('integrations')

class NullAPIClient(ProductAPIClient):
    def search(self, query: str, location: str = None) -> list[ProductDTO]:
        logger.warning("No API key configured for Product Search. NullAPIClient returning empty results.")
        return []
