from django.test import TestCase, override_settings
from django.core.exceptions import ImproperlyConfigured
from django.core.cache import cache
from decimal import Decimal
import logging
import requests
from unittest.mock import patch, MagicMock
from integrations.base import ProductDTO, ProductAPIClient
from integrations.providers.null import NullAPIClient
from integrations.providers.serpapi import SerpApiClient
from integrations.exceptions import ProductAPIUnavailable

class ProductDTOTests(TestCase):
    def test_dto_construction_success(self):
        dto = ProductDTO(
            title='Test Title',
            product_url='https://example.com/item',
            platform='amazon',
            price=Decimal('19.99'),
            image_url='https://example.com/img.jpg'
        )
        self.assertEqual(dto.title, 'Test Title')
        self.assertEqual(dto.product_url, 'https://example.com/item')
        self.assertEqual(dto.platform, 'amazon')
        self.assertEqual(dto.price, Decimal('19.99'))
        self.assertEqual(dto.image_url, 'https://example.com/img.jpg')
        self.assertIsNone(dto.rating)

    def test_dto_missing_required_fields_raises(self):
        with self.assertRaises(TypeError):
            ProductDTO(title='', product_url='https://example.com', platform='amazon')
        with self.assertRaises(TypeError):
            ProductDTO(title='Title', product_url='', platform='amazon')
        with self.assertRaises(TypeError):
            ProductDTO(title='Title', product_url='https://example.com', platform='')

class ClientInterfaceTests(TestCase):
    def test_abc_client_instantiation_raises(self):
        with self.assertRaises(TypeError):
            ProductAPIClient()

class NullAPIClientTests(TestCase):
    @patch('integrations.providers.null.logger')
    def test_null_client_returns_empty_and_logs(self, mock_logger):
        client = NullAPIClient()
        results = client.search('gaming keyboard')
        self.assertEqual(results, [])
        mock_logger.warning.assert_called_once_with(
            "No API key configured for Product Search. NullAPIClient returning empty results."
        )

class SerpApiClientTests(TestCase):
    def setUp(self):
        cache.clear()

    @override_settings(SERPAPI_API_KEY='')
    @patch('integrations.providers.serpapi.logger')
    def test_serpapi_missing_key_warning(self, mock_logger):
        client = SerpApiClient()
        results = client.search('keyboard')
        self.assertEqual(results, [])
        mock_logger.warning.assert_called_once_with(
            "SerpApi API key not configured. Falling back to empty results."
        )

    @override_settings(SERPAPI_API_KEY='fake_key')
    @patch('requests.get')
    def test_serpapi_search_success(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'shopping_results': [
                {
                    'title': 'Mechanical Keyboard',
                    'link': 'https://amazon.com/kbd',
                    'source': 'Amazon.com',
                    'price': '$29.99',
                    'thumbnail': 'https://amazon.com/img.jpg',
                    'rating': 4.5,
                    'reviews': 120
                },
                {
                    'title': 'Gaming Mouse',
                    'link': 'https://flipkart.com/mouse',
                    'source': 'Flipkart',
                    'price': 'Rs. 1,499.00',
                    'thumbnail': 'https://flipkart.com/img.jpg'
                }
            ]
        }
        mock_get.return_value = mock_response

        client = SerpApiClient()
        results = client.search('keyboard')

        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, 'Mechanical Keyboard')
        self.assertEqual(results[0].price, Decimal('29.99'))
        self.assertEqual(results[1].price, Decimal('1499.00'))

    @patch('requests.get')
    def test_timeout_and_retries_fail(self, mock_get):
        mock_get.side_effect = requests.Timeout("Connection timed out")
        mock_sleep = MagicMock()
        
        client = SerpApiClient(api_key='fake_key', sleep_func=mock_sleep)
        with self.assertRaises(ProductAPIUnavailable):
            client.search('keyboard')
            
        self.assertEqual(mock_get.call_count, 4)  # 1 initial + 3 retries
        self.assertEqual(mock_sleep.call_count, 3)

    @patch('requests.get')
    def test_timeout_then_success(self, mock_get):
        # 2 timeouts followed by 1 success
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = {'shopping_results': []}
        
        mock_get.side_effect = [
            requests.Timeout("Timeout 1"),
            requests.Timeout("Timeout 2"),
            mock_success
        ]
        mock_sleep = MagicMock()
        
        client = SerpApiClient(api_key='fake_key', sleep_func=mock_sleep)
        results = client.search('keyboard')
        
        self.assertEqual(results, [])
        self.assertEqual(mock_get.call_count, 3)
        self.assertEqual(mock_sleep.call_count, 2)

    @patch('requests.get')
    def test_rate_limit_429_retry_after(self, mock_get):
        # Mock 429 response returning Retry-After header, then a 200 success
        mock_429 = MagicMock()
        mock_429.status_code = 429
        mock_429.headers = {'Retry-After': '5'}
        
        mock_success = MagicMock()
        mock_success.status_code = 200
        mock_success.json.return_value = {'shopping_results': []}
        
        mock_get.side_effect = [mock_429, mock_success]
        mock_sleep = MagicMock()
        
        client = SerpApiClient(api_key='fake_key', sleep_func=mock_sleep)
        results = client.search('keyboard')
        
        self.assertEqual(results, [])
        self.assertEqual(mock_get.call_count, 2)
        mock_sleep.assert_called_once_with(5.0)

    @patch('requests.get')
    def test_pagination(self, mock_get):
        # Return page 1 (20 items) and page 2 (5 items)
        response1 = MagicMock()
        response1.status_code = 200
        response1.json.return_value = {
            'shopping_results': [
                {'title': f'Item {i}', 'link': f'https://amazon.com/{i}', 'source': 'Amazon', 'price': '$10'}
                for i in range(20)
            ]
        }
        
        response2 = MagicMock()
        response2.status_code = 200
        response2.json.return_value = {
            'shopping_results': [
                {'title': f'Item {i}', 'link': f'https://amazon.com/{i}', 'source': 'Amazon', 'price': '$10'}
                for i in range(20, 25)
            ]
        }
        
        mock_get.side_effect = [response1, response2]
        
        client = SerpApiClient(api_key='fake_key')
        results = client.search('keyboard')
        
        self.assertEqual(len(results), 25)
        self.assertEqual(mock_get.call_count, 2)

    @patch('requests.get')
    def test_caching_and_normalization(self, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {
            'shopping_results': [
                {'title': 'Item 1', 'link': 'https://amazon.com/1', 'source': 'Amazon', 'price': '$10'}
            ]
        }
        mock_get.return_value = mock_response
        
        client = SerpApiClient(api_key='fake_key')
        
        # First call hit network
        res1 = client.search('  Mechanical   KEYboard  ')
        self.assertEqual(len(res1), 1)
        self.assertEqual(mock_get.call_count, 1)
        
        # Second call hits cache (identical after normalization)
        res2 = client.search('mechanical keyboard')
        self.assertEqual(len(res2), 1)
        self.assertEqual(mock_get.call_count, 1)

    @patch('requests.get')
    @patch('integrations.providers.serpapi.logger')
    def test_structured_logging_redacts_key(self, mock_logger, mock_get):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {'shopping_results': []}
        mock_get.return_value = mock_response
        
        client = SerpApiClient(api_key='SECRET_API_KEY_12345')
        client.search('keyboard')
        
        self.assertTrue(mock_logger.info.called)
        log_msg = mock_logger.info.call_args[0][0]
        self.assertNotIn('SECRET_API_KEY_12345', log_msg)

class AppConfigStartupCheckTests(TestCase):
    @override_settings(PRODUCT_API_PROVIDER='serpapi', PRODUCT_API_KEY='')
    def test_startup_validation_raises_when_key_missing(self):
        from integrations.apps import IntegrationsConfig
        app_config = IntegrationsConfig('integrations', __import__('integrations'))
        with self.assertRaises(ImproperlyConfigured):
            app_config.ready()

    @override_settings(PRODUCT_API_PROVIDER='null', PRODUCT_API_KEY='')
    def test_startup_validation_passes_for_null_provider(self):
        from integrations.apps import IntegrationsConfig
        app_config = IntegrationsConfig('integrations', __import__('integrations'))
        # Should not raise any error
        app_config.ready()
