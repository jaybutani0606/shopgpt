from django.test import TestCase, override_settings
from django.core.management import call_command
from decimal import Decimal
import os
import pandas as pd
import numpy as np
from io import StringIO
from pathlib import Path

from products.models import SearchQuery, ProductResult
from products.factories import make_search_query, make_product_result
from analytics.loaders import load_results_df, clean_df
from analytics.models import AnalyticsSnapshot
from analytics.analysis import (
    aggregate_by_platform,
    value_counts_by_platform,
    describe_prices,
    filter_by_price_range,
    correlation_matrix,
    detect_price_outliers
)
from analytics.utils import (
    build_histogram_data,
    build_boxplot_data,
    build_scatter_data,
    export_chart_image,
    build_plotly_figure
)

class AnalyticsPipelineTests(TestCase):
    def setUp(self):
        self.sq = make_search_query()

    def test_df_loader_converts_to_dataframe(self):
        pr1 = make_product_result(self.sq, price='100.00', platform='amazon')
        pr2 = make_product_result(self.sq, price='150.00', platform='flipkart')

        df = load_results_df()
        self.assertEqual(len(df), 2)
        self.assertIn('platform', df.columns)
        self.assertIn('price', df.columns)
        self.assertEqual(df['price'].dtype, np.float64)

    def test_cleaning_pipeline(self):
        # 1. Missing price
        make_product_result(self.sq, price=None, platform='amazon')
        # 2. Valid item 1
        pr1 = make_product_result(self.sq, price='10.00', platform='amazon', product_url='https://a.co/1')
        # 3. Duplicate
        make_product_result(self.sq, price='12.00', platform='amazon', product_url='https://a.co/1')
        # 4. Valid item with missing rating
        pr2 = make_product_result(
            self.sq, price='20.00', platform='flipkart', product_url='https://f.co/2',
            rating=None, raw_data={}
        )

        df = load_results_df()
        clean = clean_df(df)

        self.assertEqual(len(clean), 2)
        pr2_clean = clean[clean['platform'] == 'flipkart'].iloc[0]
        self.assertEqual(pr2_clean['rating'], 'unknown')
        self.assertEqual(pr2_clean['review_count'], -1)

    def test_platform_aggregations(self):
        make_product_result(self.sq, price='10.00', platform='amazon', product_url='https://a.co/1')
        make_product_result(self.sq, price='20.00', platform='amazon', product_url='https://a.co/2')
        make_product_result(self.sq, price='30.00', platform='flipkart', product_url='https://f.co/1')
        make_product_result(self.sq, price='40.00', platform='flipkart', product_url='https://f.co/2')
        make_product_result(self.sq, price='50.00', platform='flipkart', product_url='https://f.co/3')

        df = load_results_df()
        clean = clean_df(df)
        aggs = aggregate_by_platform(clean)

        self.assertEqual(aggs.loc['amazon', 'mean'], 15.0)
        self.assertEqual(aggs.loc['amazon', 'median'], 15.0)
        self.assertEqual(aggs.loc['amazon', 'count'], 2)

        self.assertEqual(aggs.loc['flipkart', 'mean'], 40.0)
        self.assertEqual(aggs.loc['flipkart', 'median'], 40.0)
        self.assertEqual(aggs.loc['flipkart', 'count'], 3)

    def test_exploration_helpers(self):
        make_product_result(self.sq, price='10.00', platform='amazon', product_url='https://a.co/1')
        make_product_result(self.sq, price='20.00', platform='flipkart', product_url='https://f.co/1')
        make_product_result(self.sq, price='30.00', platform='croma', product_url='https://c.co/1')

        df = load_results_df()
        clean = clean_df(df)

        counts = value_counts_by_platform(clean)
        self.assertEqual(counts['amazon'], 1)

        desc = describe_prices(clean)
        self.assertEqual(desc['min'], 10.0)
        self.assertEqual(desc['max'], 30.0)

        filtered = filter_by_price_range(clean, 15.0, 25.0)
        self.assertEqual(len(filtered), 1)

    def test_correlation(self):
        make_product_result(self.sq, price='10.00', platform='amazon', product_url='https://a.co/1', raw_data={'reviews': 10})
        make_product_result(self.sq, price='20.00', platform='amazon', product_url='https://a.co/2', raw_data={'reviews': 20})
        make_product_result(self.sq, price='30.00', platform='amazon', product_url='https://a.co/3', raw_data={'reviews': 30})

        df = load_results_df()
        clean = clean_df(df)
        corr = correlation_matrix(clean)
        self.assertAlmostEqual(corr.loc['price', 'review_count'], 1.0, places=4)

    def test_outlier_detection(self):
        prices = ['10.00', '11.00', '12.00', '13.00', '14.00', '100.00']
        for i, price in enumerate(prices):
            make_product_result(self.sq, price=price, platform='flipkart', product_url=f'https://f.co/{i}')

        df = load_results_df()
        clean = clean_df(df)
        outliers = detect_price_outliers(clean)

        self.assertEqual(len(outliers), 1)
        self.assertEqual(outliers.iloc[0]['price'], 100.00)

class AnalyticsSnapshotAndCommandTests(TestCase):
    def setUp(self):
        self.sq = make_search_query()
        for i in range(5):
            make_product_result(self.sq, price=str(10.0 + i), platform='amazon', product_url=f'https://a.co/{i}', rating='4.0')
            make_product_result(self.sq, price=str(20.0 + i), platform='flipkart', product_url=f'https://f.co/{i}', rating='5.0')

    def test_snapshot_model_lifecycle(self):
        df = load_results_df()
        clean = clean_df(df)
        snapshot = AnalyticsSnapshot.create_from(clean)
        
        self.assertIsNotNone(snapshot.id)
        self.assertEqual(AnalyticsSnapshot.latest(), snapshot)
        self.assertIn('aggregations', snapshot.data)
        self.assertIn('amazon', snapshot.data['aggregations'])

    def test_refresh_analytics_management_command(self):
        out = StringIO()
        call_command('refresh_analytics', stdout=out)
        self.assertIn('Successfully created analytics snapshot', out.getvalue())
        
        latest = AnalyticsSnapshot.latest()
        self.assertIsNotNone(latest)

    def test_histogram_data_builder(self):
        df = load_results_df()
        clean = clean_df(df)
        hist = build_histogram_data(clean, bins=5)
        
        self.assertIsNotNone(hist)
        self.assertTrue(len(hist) <= 5)
        self.assertIn('bin_start', hist[0])

    def test_boxplot_data_builder(self):
        df = load_results_df()
        clean = clean_df(df)
        box = build_boxplot_data(clean)
        
        self.assertIn('amazon', box)
        self.assertEqual(box['amazon']['median'], 12.0)
        self.assertEqual(box['amazon']['min'], 10.0)
        self.assertEqual(box['amazon']['max'], 14.0)

    def test_scatter_data_builder(self):
        make_product_result(self.sq, price='99.99', platform='amazon', rating='not-a-number', product_url='https://a.co/unparseable')
        
        df = load_results_df()
        clean = clean_df(df)
        scatter = build_scatter_data(clean)
        
        self.assertTrue(len(scatter) > 0)
        for pt in scatter:
            self.assertIsInstance(pt['price'], float)
            self.assertIsInstance(pt['rating'], float)
            self.assertNotEqual(pt['price'], 99.99)

    def test_seaborn_static_image_export(self):
        df = load_results_df()
        clean = clean_df(df)
        
        path = export_chart_image('boxplot', clean)
        self.assertTrue(path.exists())
        self.assertTrue(path.stat().st_size > 0)
        
        # Verify it has valid PNG signature bytes
        with open(path, 'rb') as f:
            sig = f.read(8)
        self.assertEqual(sig, b'\x89PNG\r\n\x1a\n')
            
        os.remove(path)

    def test_plotly_figure_builders(self):
        df = load_results_df()
        clean = clean_df(df)
        
        fig = build_plotly_figure('histogram', clean)
        self.assertIn('data', fig)
        self.assertEqual(fig['data'][0]['type'], 'histogram')
        
        fig_box = build_plotly_figure('boxplot', clean)
        self.assertIn('data', fig_box)
        self.assertEqual(fig_box['data'][0]['type'], 'box')
        
        fig_scatter = build_plotly_figure('scatter', clean)
        self.assertIn('data', fig_scatter)
        self.assertEqual(fig_scatter['data'][0]['type'], 'scatter')

from django.contrib.auth import get_user_model
from django.urls import reverse

class AnalyticsDashboardViewTests(TestCase):
    def setUp(self):
        self.User = get_user_model()
        self.user = self.User.objects.create_user(username='AnalyticsUser', password='password123')
        self.sq = make_search_query(user=self.user)
        make_product_result(self.sq, price='100.00', platform='amazon')

    def test_dashboard_anonymous_redirects(self):
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 302)

    def test_dashboard_authenticated_succeeds(self):
        self.client.login(username='AnalyticsUser', password='password123')
        response = self.client.get(reverse('analytics:dashboard'))
        self.assertEqual(response.status_code, 200)

