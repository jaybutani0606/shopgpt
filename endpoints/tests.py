from django.contrib.auth.models import User
from django.urls import reverse
from testing import BaseTestCase
from analytics.models import AnalyticsSnapshot
from products.models import ProductResult, SearchQuery
from decimal import Decimal

class EndpointsTests(BaseTestCase):
    def setUp(self):
        super().setUp()
        self.user = self.make_user(username="endpoint_user", password="securepassword")
        self.client.login(username="endpoint_user", password="securepassword")
        
    def test_anonymous_requests_redirected(self):
        self.client.logout()
        url = reverse('endpoints:analytics_summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 302)
        self.assertIn('/accounts/login/', response.url)

    def test_analytics_summary_not_computed(self):
        url = reverse('endpoints:analytics_summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['status'], 'not computed yet')

    def test_analytics_summary_success(self):
        snapshot = AnalyticsSnapshot.objects.create(data={"aggregations": {"amazon": {"mean": 100}}})
        url = reverse('endpoints:analytics_summary')
        response = self.client.get(url)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()['aggregations']['amazon']['mean'], 100)

    def test_analytics_chart_valid(self):
        # Create some results so load_results_df works
        sq = SearchQuery.objects.create(query="keyboard")
        ProductResult.objects.create(
            search=sq, platform="amazon", title="Mechanical Keyboard",
            price=Decimal("1500.00"), rating="4.5", product_url="http://amazon.in/1"
        )
        for name in ['histogram', 'boxplot', 'scatter']:
            url = reverse('endpoints:analytics_chart', kwargs={'name': name})
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
            self.assertIn('data', response.json())
            self.assertIn('layout', response.json())

    def test_analytics_chart_invalid(self):
        url = reverse('endpoints:analytics_chart', kwargs={'name': 'invalid_name'})
        response = self.client.get(url)
        self.assertEqual(response.status_code, 404)
        self.assertIn('error', response.json())

    def test_throttling_triggers(self):
        url = reverse('endpoints:analytics_summary')
        # Trigger 60 requests to hit the throttle limit (which is 60)
        # Let's perform a smaller limit test by overriding throttle_session behavior, or simply sending 61 requests.
        # Since 61 requests takes time, we can send requests and verify response status codes.
        # But wait, 61 requests is fast in local SQLite tests, usually takes less than 0.1s!
        # Let's send 61 requests.
        for i in range(60):
            response = self.client.get(url)
            self.assertEqual(response.status_code, 200)
        
        # The 61st request should trigger 429
        response = self.client.get(url)
        self.assertEqual(response.status_code, 429)
        self.assertIn('Retry-After', response.headers)
