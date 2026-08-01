from django.contrib.auth import get_user_model
from products.models import SearchQuery, ProductResult

def make_search_query(**kwargs):
    User = get_user_model()
    if 'user' not in kwargs:
        user, _ = User.objects.get_or_create(username='default_factory_user')
        kwargs['user'] = user
    if 'query' not in kwargs:
        kwargs['query'] = 'test product'
    return SearchQuery.objects.create(**kwargs)

def make_product_result(search, **kwargs):
    if 'platform' not in kwargs:
        kwargs['platform'] = 'amazon'
    if 'title' not in kwargs:
        kwargs['title'] = 'Test Product'
    if 'price' not in kwargs:
        kwargs['price'] = '99.99'
    if 'price_str' not in kwargs:
        kwargs['price_str'] = 'Rs. 99.99'
    if 'product_url' not in kwargs:
        kwargs['product_url'] = 'https://example.com/test-product'
    return ProductResult.objects.create(search=search, **kwargs)
