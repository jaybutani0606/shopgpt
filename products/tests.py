from django.core.exceptions import ValidationError
from django.contrib.auth import get_user_model
from django.urls import reverse
from django.test import override_settings
from django.utils import timezone
from datetime import timedelta
from testing import BaseTestCase
from products.models import SearchQuery, ProductResult
from products.services import save_results
from products.factories import make_search_query, make_product_result

class ProductModelsTests(BaseTestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.make_user(username='TestUser')

    def test_search_query_creation_defaults(self):
        sq = SearchQuery.objects.create(
            user=self.user,
            query='mechanical keyboard'
        )
        self.assertEqual(sq.status, 'pending')
        self.assertEqual(sq.result_count, 0)
        self.assertEqual(str(sq), 'mechanical keyboard')

        sq2 = SearchQuery.objects.create(
            user=self.user,
            query='gaming mouse'
        )
        SearchQuery.objects.filter(pk=sq.pk).update(timestamp=timezone.now() - timedelta(seconds=10))

        queries = list(SearchQuery.objects.all())
        self.assertEqual(queries[0], sq2)
        self.assertEqual(queries[1], sq)

    def test_search_query_validation(self):
        sq = SearchQuery(
            user=self.user,
            query='mechanical keyboard',
            status='invalid_status'
        )
        with self.assertRaises(ValidationError):
            sq.full_clean()

    def test_product_result_creation_defaults(self):
        sq = SearchQuery.objects.create(
            user=self.user,
            query='mechanical keyboard'
        )
        pr = ProductResult.objects.create(
            search=sq,
            platform='flipkart',
            title='Kreo mechanical keyboard',
            price=2999.00,
            price_str='Rs. 2,999',
            product_url='https://example.com/keyboard'
        )
        self.assertEqual(pr.is_real_data, True)
        self.assertEqual(str(pr), 'Kreo mechanical keyboard - flipkart')

    def test_product_result_validators(self):
        sq = make_search_query(user=self.user)
        
        # Test negative price
        with self.assertRaises(ValidationError):
            ProductResult.objects.create(
                search=sq,
                platform='amazon',
                title='Negative Price Keyboard',
                price=-100.00,
                product_url='https://example.com/test'
            )

        # Test malformed URL
        with self.assertRaises(ValidationError):
            ProductResult.objects.create(
                search=sq,
                platform='amazon',
                title='Bad URL Keyboard',
                price=100.00,
                product_url='invalid-url-format'
            )

        # Test empty platform
        with self.assertRaises(ValidationError):
            ProductResult.objects.create(
                search=sq,
                platform='',
                title='Empty Platform Keyboard',
                price=100.00,
                product_url='https://example.com/test'
            )

    def test_search_query_status_helpers(self):
        sq = make_search_query(user=self.user)
        self.assertEqual(sq.status, 'pending')

        # Test mark_completed
        sq.mark_completed(5)
        sq.refresh_from_db()
        self.assertEqual(sq.status, 'completed')
        self.assertEqual(sq.result_count, 5)

        # Test mark_failed
        sq2 = make_search_query(user=self.user)
        sq2.mark_failed('API Rate Limited')
        sq2.refresh_from_db()
        self.assertEqual(sq2.status, 'failed')
        self.assertEqual(sq2.result_count, 0) # untouched

    def test_recent_for_user_manager(self):
        user2 = self.make_user(username='User2')
        # Create searches for user1 and user2
        sq_u1_1 = make_search_query(user=self.user, query='u1 q1')
        sq_u1_2 = make_search_query(user=self.user, query='u1 q2')
        sq_u2_1 = make_search_query(user=user2, query='u2 q1')

        # Force query 1 to be older
        SearchQuery.objects.filter(pk=sq_u1_1.pk).update(timestamp=timezone.now() - timedelta(seconds=10))

        recent = SearchQuery.objects.recent_for_user(self.user)
        self.assertEqual(len(recent), 2)
        self.assertEqual(recent[0], sq_u1_2)
        self.assertEqual(recent[1], sq_u1_1)

        # Respect limit
        limit_recent = SearchQuery.objects.recent_for_user(self.user, limit=1)
        self.assertEqual(len(limit_recent), 1)
        self.assertEqual(limit_recent[0], sq_u1_2)

        # Anonymous user returns empty
        from django.contrib.auth.models import AnonymousUser
        anon_recent = SearchQuery.objects.recent_for_user(AnonymousUser())
        self.assertEqual(len(anon_recent), 0)

    def test_for_search_manager(self):
        sq1 = make_search_query(user=self.user, query='sq1')
        sq2 = make_search_query(user=self.user, query='sq2')

        # Results for search 1
        pr_sq1_high = make_product_result(sq1, price=500.00, title='High Price')
        pr_sq1_low = make_product_result(sq1, price=100.00, title='Low Price')
        # Result for search 2
        pr_sq2 = make_product_result(sq2, price=200.00)

        results = ProductResult.objects.for_search(sq1)
        self.assertEqual(len(results), 2)
        # Verify ordering is price ascending by default
        self.assertEqual(results[0], pr_sq1_low)
        self.assertEqual(results[1], pr_sq1_high)

    def test_save_results_service(self):
        sq = make_search_query(user=self.user)
        dtos = [
            {'platform': 'amazon', 'title': 'Item 1', 'price': 10.00, 'product_url': 'https://a.co/1'},
            {'platform': 'flipkart', 'title': 'Item 2', 'price': 20.00, 'product_url': 'https://f.co/2'},
        ]
        save_results(sq, dtos)
        
        sq.refresh_from_db()
        self.assertEqual(sq.status, 'completed')
        self.assertEqual(sq.result_count, 2)
        
        results = ProductResult.objects.for_search(sq)
        self.assertEqual(len(results), 2)
        self.assertEqual(results[0].title, 'Item 1')

    def test_factories(self):
        sq = make_search_query()
        self.assertIsNotNone(sq.id)
        sq.full_clean()

        pr = make_product_result(sq)
        self.assertIsNotNone(pr.id)
        pr.full_clean()

class ProductsAdminTests(BaseTestCase):
    def setUp(self):
        self.User = get_user_model()
        self.admin_user = self.User.objects.create_superuser(
            username='adminuser',
            password='adminpassword123',
            email='admin@example.com'
        )

    def test_admin_pages_accessible(self):
        self.client.login(username='adminuser', password='adminpassword123')
        
        url = reverse('admin:products_searchquery_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        
        url = reverse('admin:products_productresult_changelist')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)

from decimal import Decimal
from unittest.mock import patch, MagicMock
from products.services import SearchService, deduplicate_dtos, dispatch_search, is_celery_reachable
from integrations.base import ProductDTO
from integrations.exceptions import ProductAPIUnavailable

class SearchServiceTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.User = get_user_model()
        self.user = self.make_user(username='SearchServiceUser')

    @override_settings(PRODUCT_API_PROVIDER='serpapi', PRODUCT_API_KEY='fake')
    @patch('products.services.get_api_client')
    def test_search_service_successful_run(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search.return_value = [
            ProductDTO(title='Mechanical Keyboard', product_url='https://amazon.com/kbd', platform='amazon', price=Decimal('29.99')),
            ProductDTO(title='Gaming Mouse', product_url='https://flipkart.com/mouse', platform='flipkart', price=Decimal('9.99'))
        ]
        mock_get_client.return_value = mock_client

        sq = make_search_query(user=self.user)
        SearchService.run('keyboard', sq.id)

        sq.refresh_from_db()
        self.assertEqual(sq.status, 'completed')
        self.assertEqual(sq.result_count, 2)
        
        results = list(ProductResult.objects.filter(search=sq))
        self.assertEqual(len(results), 2)

    def test_deduplication_logic(self):
        dtos = [
            ProductDTO(title='Mechanical Keyboard', product_url='https://amazon.com/kbd', platform='amazon', price=Decimal('29.99')),
            ProductDTO(title='Mechanical Keyboard', product_url='https://amazon.com/kbd?utm_source=test', platform='amazon', price=Decimal('29.99')),
            ProductDTO(title='MECHANICAL KEYBOARD', product_url='https://amazon.com/kbd-alt', platform='amazon', price=Decimal('29.99')),
            ProductDTO(title='Gaming Mouse', product_url='https://amazon.com/mouse', platform='amazon', price=Decimal('9.99'))
        ]
        
        unique = deduplicate_dtos(dtos)
        self.assertEqual(len(unique), 2)
        self.assertEqual(unique[0].title, 'Mechanical Keyboard')
        self.assertEqual(unique[1].title, 'Gaming Mouse')

    @override_settings(PRODUCT_API_PROVIDER='serpapi', PRODUCT_API_KEY='fake')
    @patch('products.services.get_api_client')
    def test_error_state_mapping_unavailable(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search.side_effect = ProductAPIUnavailable("Service Unavailable")
        mock_get_client.return_value = mock_client

        sq = make_search_query(user=self.user)
        SearchService.run('keyboard', sq.id)

        sq.refresh_from_db()
        self.assertEqual(sq.status, 'failed')
        self.assertEqual(sq.failure_reason, 'api_unavailable')

    @override_settings(PRODUCT_API_PROVIDER='null', PRODUCT_API_KEY='')
    def test_error_state_mapping_not_configured(self):
        sq = make_search_query(user=self.user)
        SearchService.run('keyboard', sq.id)

        sq.refresh_from_db()
        self.assertEqual(sq.status, 'failed')
        self.assertEqual(sq.failure_reason, 'not_configured')

    @override_settings(PRODUCT_API_PROVIDER='serpapi', PRODUCT_API_KEY='fake')
    @patch('products.services.get_api_client')
    def test_error_state_mapping_no_results(self, mock_get_client):
        mock_client = MagicMock()
        mock_client.search.return_value = []
        mock_get_client.return_value = mock_client

        sq = make_search_query(user=self.user)
        SearchService.run('keyboard', sq.id)

        sq.refresh_from_db()
        self.assertEqual(sq.status, 'completed')
        self.assertEqual(sq.result_count, 0)

    @patch('socket.create_connection')
    def test_celery_unreachable_fallback_dispatch(self, mock_connect):
        mock_connect.side_effect = Exception("Connection timed out")
        
        sq = make_search_query(user=self.user)
        with patch('products.services.SearchService.run') as mock_run:
            dispatch_search('keyboard', sq.id)
            mock_run.assert_called_once_with('keyboard', sq.id)

    @patch('socket.create_connection')
    @patch('products.tasks.run_search_task.delay')
    def test_celery_reachable_dispatch(self, mock_delay, mock_connect):
        mock_connect.return_value = MagicMock()
        
        sq = make_search_query(user=self.user)
        dispatch_search('keyboard', sq.id)
        mock_delay.assert_called_once_with('keyboard', sq.id)

class ProductViewsTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.User = get_user_model()
        self.user = self.make_user(username='ViewTestUser')
        self.client.force_login(self.user)

    @patch('products.views.dispatch_search')
    def test_search_view_post_valid_query(self, mock_dispatch):
        response = self.client.post(reverse('products:search'), {'query': 'mechanical keyboard'})
        
        sq = SearchQuery.objects.latest('id')
        self.assertEqual(sq.query, 'mechanical keyboard')
        self.assertEqual(sq.user, self.user)
        self.assertRedirects(response, reverse('products:results', kwargs={'search_id': sq.id}))
        mock_dispatch.assert_called_once_with('mechanical keyboard', sq.id)

    def test_search_view_post_empty_query(self):
        response = self.client.post(reverse('products:search'), {'query': ' '})
        self.assertRedirects(response, reverse('home'))

        messages = list(response.wsgi_request._messages)
        self.assertEqual(len(messages), 1)
        self.assertEqual(str(messages[0]), "Search query cannot be empty.")

    def test_results_view_status_contexts(self):
        sq_completed = make_search_query(user=self.user, query='completed kbd', status='completed', result_count=1)
        pr = make_product_result(sq_completed, price='99.99')
        
        response = self.client.get(reverse('products:results', kwargs={'search_id': sq_completed.id}))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'completed kbd')
        self.assertContains(response, '99.99')
        self.assertIsNone(response.context['error_message'])

        sq_empty = make_search_query(user=self.user, query='empty kbd', status='completed', result_count=0)
        response = self.client.get(reverse('products:results', kwargs={'search_id': sq_empty.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['error_message'], "No matching products found.")

        sq_failed_api = make_search_query(user=self.user, status='failed', failure_reason='api_unavailable')
        response = self.client.get(reverse('products:results', kwargs={'search_id': sq_failed_api.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['error_message'], "The search API is currently unavailable. Please try again later.")

        sq_failed_config = make_search_query(user=self.user, status='failed', failure_reason='not_configured')
        response = self.client.get(reverse('products:results', kwargs={'search_id': sq_failed_config.id}))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context['error_message'], "Search provider is not configured. Please setup your API keys.")

    def test_comparison_view_sorting(self):
        sq = make_search_query(user=self.user, query='kbd')
        pr_low = make_product_result(sq, price='10.00', rating='4.0', title='Low Price')
        pr_high = make_product_result(sq, price='100.00', rating='5.0', title='High Price')

        response = self.client.get(reverse('products:compare', kwargs={'search_id': sq.id}))
        self.assertEqual(list(response.context['results']), [pr_low, pr_high])

        response = self.client.get(reverse('products:compare', kwargs={'search_id': sq.id}) + '?sort=price&dir=desc')
        self.assertEqual(list(response.context['results']), [pr_high, pr_low])

        response = self.client.get(reverse('products:compare', kwargs={'search_id': sq.id}) + '?sort=rating&dir=desc')
        self.assertEqual(list(response.context['results']), [pr_high, pr_low])

        response = self.client.get(reverse('products:compare', kwargs={'search_id': sq.id}) + '?sort=invalid')
        self.assertEqual(list(response.context['results']), [pr_low, pr_high])

    def test_comparison_view_platform_filtering(self):
        sq = make_search_query(user=self.user, query='kbd')
        pr_amz = make_product_result(sq, price='10.00', rating='4.0', title='Amazon Item')
        pr_amz.platform = 'amazon'
        pr_amz.save()
        pr_flp = make_product_result(sq, price='20.00', rating='4.5', title='Flipkart Item')
        pr_flp.platform = 'flipkart'
        pr_flp.save()

        response = self.client.get(reverse('products:compare', kwargs={'search_id': sq.id}) + '?platform=amazon')
        self.assertEqual(list(response.context['results']), [pr_amz])

        response = self.client.get(reverse('products:compare', kwargs={'search_id': sq.id}) + '?platform=flipkart')
        self.assertEqual(list(response.context['results']), [pr_flp])

    def test_top_recommendations_ranking(self):
        sq = make_search_query(user=self.user)
        pr_oos = make_product_result(sq, price='5.00', title='OOS item', raw_data={'in_stock': False})
        pr1 = make_product_result(sq, price='20.00', title='Cheap', raw_data={'in_stock': True})
        pr2 = make_product_result(sq, price='50.00', title='Mid', raw_data={'in_stock': True})
        pr3 = make_product_result(sq, price='80.00', title='High', raw_data={'in_stock': True})
        pr4 = make_product_result(sq, price='100.00', title='Expensive', raw_data={'in_stock': True})

        response = self.client.get(reverse('products:recommendations', kwargs={'search_id': sq.id}))
        self.assertEqual(response.status_code, 200)
        
        recs = response.context['recommendations']
        self.assertEqual(len(recs), 3)
        self.assertEqual(recs[0]['product'], pr1)
        self.assertEqual(recs[0]['reason'], "Lowest price among in-stock listings for this search (ranked by price)")
        self.assertEqual(recs[1]['product'], pr2)
        self.assertEqual(recs[2]['product'], pr3)

    @patch('ml.services.predict_fair_price')
    @patch('ml.services.predict_deal_quality')
    def test_top_recommendations_ml_backed(self, mock_deal, mock_fair):
        mock_fair.return_value = Decimal("100.00")
        mock_deal.return_value = "great_deal"

        sq = make_search_query(user=self.user)
        pr = make_product_result(sq, price='80.00', title='Keyboard', raw_data={'in_stock': True})

        response = self.client.get(reverse('products:recommendations', kwargs={'search_id': sq.id}))
        self.assertEqual(response.status_code, 200)
        
        recs = response.context['recommendations']
        self.assertEqual(len(recs), 1)
        self.assertEqual(recs[0]['product'], pr)
        self.assertEqual(recs[0]['reason'], "20% below the typical fair price for this product. (Estimated Fair Price: 100.00)")

    def test_history_view_security(self):
        make_search_query(user=self.user, query='user1 search')
        user2 = self.make_user(username='User2')
        make_search_query(user=user2, query='user2 search')

        response = self.client.get(reverse('products:history'))
        self.assertEqual(response.status_code, 200)
        
        object_list = response.context['object_list']
        self.assertEqual(len(object_list), 1)
        self.assertEqual(object_list[0].query, 'user1 search')


