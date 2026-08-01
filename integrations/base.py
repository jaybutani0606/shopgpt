from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from decimal import Decimal

@dataclass
class ProductDTO:
    title: str
    product_url: str
    platform: str
    price: Decimal | None = None
    price_str: str | None = None
    currency: str | None = None
    image_url: str | None = None
    rating: str | None = None
    review_count: int | None = None
    in_stock: bool | None = None
    raw_payload: dict = field(default_factory=dict)

    def __post_init__(self):
        # Enforce required fields validation at creation time
        if not self.title or not isinstance(self.title, str):
            raise TypeError("title is required and must be a string")
        if not self.product_url or not isinstance(self.product_url, str):
            raise TypeError("product_url is required and must be a string")
        if not self.platform or not isinstance(self.platform, str):
            raise TypeError("platform is required and must be a string")

class ProductAPIClient(ABC):
    @abstractmethod
    def search(self, query: str, location: str = None) -> list[ProductDTO]:
        pass
