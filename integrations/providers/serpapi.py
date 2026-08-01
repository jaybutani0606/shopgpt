import logging
import requests
import re
import time
from decimal import Decimal
from django.conf import settings
from django.core.cache import cache
from integrations.base import ProductAPIClient, ProductDTO
from integrations.exceptions import ProductAPIUnavailable

logger = logging.getLogger('integrations')

class SerpApiClient(ProductAPIClient):
    def __init__(self, api_key=None, sleep_func=time.sleep):
        self.api_key = api_key or getattr(settings, 'SERPAPI_API_KEY', None)
        self.sleep_func = sleep_func
        self.timeout = getattr(settings, 'PRODUCT_API_TIMEOUT', 10)
        self.max_retries = getattr(settings, 'PRODUCT_API_MAX_RETRIES', 3)
        self.results_limit = getattr(settings, 'PRODUCT_RESULTS_LIMIT', 40)

    def search(self, query: str, location: str = None) -> list[ProductDTO]:
        if not self.api_key:
            logger.warning("SerpApi API key not configured. Falling back to empty results.")
            return []

        # Cache lookup using normalized query & location
        normalized_query = " ".join(query.lower().strip().split())
        normalized_loc = " ".join(location.lower().strip().split()) if location else 'india'
        cache_key = f"product_search_cache:{normalized_query}:{normalized_loc}"
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            logger.info(f"Cache hit for query: '{query}', location: '{normalized_loc}'")
            return cached_data

        url = "https://serpapi.com/search.json"
        params = {
            "engine": "google_shopping",
            "q": query,
            "api_key": self.api_key,
            "gl": "in",
            "hl": "en",
            "google_domain": "google.co.in",
        }
        if location:
            params['location'] = location

        results = []
        start = 0
        
        while len(results) < self.results_limit:
            params['start'] = start
            start_time = time.perf_counter()
            try:
                raw_json = self.get_with_resilience(url, params)
            except ProductAPIUnavailable as e:
                logger.error(f"Failed to fetch page start={start} for query='{query}': {e}")
                if not results:
                    raise
                break

            latency = time.perf_counter() - start_time
            page_results = self.parse_response(raw_json)
            
            # Log metrics (explicitly redact key)
            logged_url = "https://serpapi.com/search.json"
            logger.info(
                f"Outbound SerpApi call: query='{query}', start={start}, url='{logged_url}', "
                f"latency={latency:.3f}s, page_count={len(page_results)}"
            )

            if not page_results:
                break

            results.extend(page_results)
            if len(page_results) < 10:
                break
            start += 20

        final_results = results[:self.results_limit]
        # Store in cache
        cache.set(cache_key, final_results, timeout=1800)
        return final_results

    def get_with_resilience(self, url: str, params: dict) -> dict:
        attempt = 0
        while True:
            try:
                response = requests.get(url, params=params, timeout=self.timeout)
                if response.status_code == 429:
                    attempt += 1
                    if attempt > self.max_retries:
                        raise ProductAPIUnavailable("Rate limit (429) hit, max retries exceeded.")
                    
                    retry_after = response.headers.get("Retry-After")
                    if retry_after:
                        try:
                            sleep_delay = float(retry_after)
                        except ValueError:
                            sleep_delay = 2 ** attempt
                    else:
                        sleep_delay = 2 ** attempt

                    logger.warning(f"SerpApi rate limited (429). Retrying after {sleep_delay}s...")
                    self.sleep_func(sleep_delay)
                    continue

                response.raise_for_status()
                return response.json()

            except (requests.RequestException, requests.Timeout, ValueError) as e:
                attempt += 1
                if attempt > self.max_retries:
                    raise ProductAPIUnavailable(f"Request failed after max retries: {e}") from e
                
                sleep_delay = 2 ** attempt
                logger.warning(f"SerpApi request failed ({e}). Retrying in {sleep_delay}s...")
                self.sleep_func(sleep_delay)

    def parse_response(self, raw_json: dict) -> list[ProductDTO]:
        results = []
        shopping_results = raw_json.get('shopping_results', [])
        
        for item in shopping_results:
            title = item.get('title')
            product_url = item.get('link') or item.get('product_link')
            
            source = item.get('source', '')
            platform = self.map_platform(source, product_url)

            if not title or not product_url or not platform:
                logger.warning(
                    f"Skipping malformed search result item. Missing required fields: "
                    f"title={title}, product_url={product_url}, platform={platform}"
                )
                continue
                
            raw_price = item.get('price')
            price = self.extract_price(raw_price)
            
            dto = ProductDTO(
                title=title,
                product_url=product_url,
                platform=platform,
                price=price,
                price_str=raw_price,
                image_url=item.get('thumbnail'),
                rating=str(item.get('rating')) if item.get('rating') is not None else None,
                review_count=item.get('reviews'),
                in_stock=None,
                raw_payload=item
            )
            results.append(dto)
            
        return results

    def map_platform(self, source: str, product_url: str = None) -> str | None:
        platform = None
        if source:
            source_lower = source.lower().strip()
            if 'amazon' in source_lower:
                platform = 'amazon'
            elif 'flipkart' in source_lower:
                platform = 'flipkart'
            elif 'meesho' in source_lower:
                platform = 'meesho'
            elif 'croma' in source_lower:
                platform = 'croma'
            elif 'reliance' in source_lower or 'digital' in source_lower:
                platform = 'reliance'
            elif 'ajio' in source_lower:
                platform = 'ajio'
            elif 'myntra' in source_lower:
                platform = 'myntra'
            elif 'tatacliq' in source_lower or 'tata cliq' in source_lower:
                platform = 'tatacliq'
            elif 'nykaa' in source_lower:
                platform = 'nykaa'
            elif 'snapdeal' in source_lower:
                platform = 'snapdeal'

        if not platform and product_url:
            from urllib.parse import urlparse
            try:
                domain = urlparse(product_url).netloc.lower()
                if 'amazon' in domain:
                    platform = 'amazon'
                elif 'flipkart' in domain:
                    platform = 'flipkart'
                elif 'meesho' in domain:
                    platform = 'meesho'
                elif 'croma' in domain:
                    platform = 'croma'
                elif 'reliance' in domain or 'reliancedigital' in domain:
                    platform = 'reliance'
                elif 'ajio' in domain:
                    platform = 'ajio'
                elif 'myntra' in domain:
                    platform = 'myntra'
                elif 'tatacliq' in domain:
                    platform = 'tatacliq'
                elif 'nykaa' in domain:
                    platform = 'nykaa'
                elif 'snapdeal' in domain:
                    platform = 'snapdeal'
            except Exception:
                pass
        return platform


    def extract_price(self, price_str: str) -> Decimal | None:
        if not price_str:
            return None
        match = re.search(r'\d[\d.,]*', str(price_str))
        if match:
            clean_num = match.group(0).replace(',', '')
            try:
                return Decimal(clean_num)
            except Exception:
                pass
        return None
