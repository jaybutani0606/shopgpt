from products.models import ProductResult, SearchQuery
from django.db import transaction
import urllib.parse
from difflib import SequenceMatcher
import logging
import socket
from django.conf import settings
from integrations.providers.null import NullAPIClient
from integrations.providers.serpapi import SerpApiClient
from integrations.exceptions import ProductAPIUnavailable

logger = logging.getLogger('products')

def save_results(search, dtos):
    results = []
    for dto in dtos:
        get_val = lambda obj, key, default=None: getattr(obj, key, default) if hasattr(obj, key) else (obj.get(key, default) if isinstance(obj, dict) else default)
        product_url = get_val(dto, 'product_url')
        if product_url:
            product_url = product_url.replace(' ', '%20')
        image_url = get_val(dto, 'image_url')
        if image_url:
            image_url = image_url.replace(' ', '%20')

        results.append(ProductResult(
            search=search,
            platform=get_val(dto, 'platform'),
            title=get_val(dto, 'title'),
            price=get_val(dto, 'price'),
            price_str=get_val(dto, 'price_str'),
            image_url=image_url,
            product_url=product_url,
            rating=get_val(dto, 'rating'),
            raw_data=get_val(dto, 'raw_data'),
            is_real_data=get_val(dto, 'is_real_data', True),
            category=get_val(dto, 'category'),
        ))
    from django.core.exceptions import ValidationError
    valid_results = []
    for res in results:
        try:
            res.full_clean()
            valid_results.append(res)
        except ValidationError as e:
            logger.warning(
                f"Skipping saving product result '{res.title}' due to validation error: {e}"
            )

    with transaction.atomic():
        ProductResult.objects.bulk_create(valid_results)
        search.mark_completed(len(valid_results))

def get_api_client():
    provider = getattr(settings, 'PRODUCT_API_PROVIDER', 'null')
    if provider == 'serpapi':
        return SerpApiClient()
    return NullAPIClient()

def normalize_url(url):
    if not url:
        return ''
    try:
        parsed = urllib.parse.urlparse(url)
        query_params = urllib.parse.parse_qsl(parsed.query)
        tracking_params = {'utm_source', 'utm_medium', 'utm_campaign', 'ref', 'tag', 'qid', 'sr'}
        clean_params = [(k, v) for k, v in query_params if k.lower() not in tracking_params]
        clean_params.sort()
        new_query = urllib.parse.urlencode(clean_params)
        # Keep query parameters intact for important routing (like Google Shopping engines)
        return urllib.parse.urlunparse((parsed.scheme, parsed.netloc, parsed.path, parsed.params, new_query, ''))
    except Exception:
        return url

def deduplicate_dtos(dtos):
    seen_urls = set()
    unique_dtos = []
    
    for dto in dtos:
        norm_url = normalize_url(dto.product_url)
        if norm_url in seen_urls:
            continue
            
        is_duplicate = False
        for existing in unique_dtos:
            if existing.platform == dto.platform:
                similarity = SequenceMatcher(None, existing.title.lower(), dto.title.lower()).ratio()
                if similarity > 0.85:
                    is_duplicate = True
                    break
                    
        if not is_duplicate:
            if norm_url:
                seen_urls.add(norm_url)
            unique_dtos.append(dto)
            
    return unique_dtos

def is_celery_reachable():
    broker_url = getattr(settings, 'CELERY_BROKER_URL', '')
    if not broker_url:
        return False
    try:
        parsed = urllib.parse.urlparse(broker_url)
        host = parsed.hostname or 'localhost'
        port = parsed.port or 6379
        s = socket.create_connection((host, port), timeout=0.2)
        s.close()
        return True
    except Exception:
        return False

def dispatch_search(query, search_id):
    if is_celery_reachable():
        try:
            from products.tasks import run_search_task
            run_search_task.delay(query, search_id)
            return
        except Exception as e:
            logger.warning(f"Failed to dispatch Celery task: {e}. Falling back to sync.")
    
    # Sync fallback
    SearchService.run(query, search_id)

class SearchService:
    @staticmethod
    def run(query, search_id):
        try:
            search = SearchQuery.objects.get(pk=search_id)
        except SearchQuery.DoesNotExist:
            logger.error(f"SearchQuery ID {search_id} not found.")
            return

        client = get_api_client()
        if isinstance(client, NullAPIClient):
            search.mark_failed("not_configured")
            return

        try:
            dtos = client.search(query, location=getattr(search, 'location', 'India'))
            if not dtos:
                search.mark_completed(0)
                return
                
            unique_dtos = deduplicate_dtos(dtos)
            save_results(search, unique_dtos)
            
        except ProductAPIUnavailable:
            search.mark_failed("api_unavailable")
        except Exception as e:
            logger.error(f"Unexpected search service error: {e}")
            search.mark_failed("unexpected_error")
