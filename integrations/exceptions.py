class ProductAPIUnavailable(Exception):
    """Raised when the product search API is down or retries have been exhausted."""
    pass
