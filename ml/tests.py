from django.test import TestCase, override_settings
from django.core.management import call_command
from django.urls import reverse
from unittest.mock import patch, MagicMock
from decimal import Decimal
import os
import joblib
import pandas as pd
import numpy as np
from io import StringIO
from pathlib import Path

from products.models import SearchQuery, ProductResult
from products.factories import make_search_query, make_product_result
from integrations.base import ProductDTO
from ml.features import build_features, build_training_table
from ml.models import (
    split_train_val,
    train_linear_model,
    train_polynomial_model,
    evaluate,
    compare_models,
    get_artifacts_dir,
    train_random_forest_classifier,
    train_logistic_regression_classifier,
    evaluate_classifier,
    compare_classifiers,
)
from ml.services import predict_fair_price, predict_deal_quality, DEAL_BADGE_MAP
from ml.labels import assign_deal_labels, build_deal_training_table, GREAT_DEAL_THRESHOLD, OVERPRICED_THRESHOLD

class MLPipelineTests(TestCase):
    def setUp(self):
        self.sq = make_search_query()
        # Seed training rows
        for i in range(12):
            # linear relationship: price = 10 * rating
            rating_val = float(i + 1)
            price_val = 10.0 * rating_val
            make_product_result(
                self.sq,
                price=str(price_val),
                rating=str(rating_val),
                platform='amazon' if i % 2 == 0 else 'flipkart',
                product_url=f'https://site.com/{i}',
                category='electronics'
            )

    def test_feature_matrix_generation(self):
        df = pd.DataFrame([{
            'platform': 'amazon',
            'category': 'electronics',
            'rating': '4.5',
            'review_count': 100,
            'raw_data': {}
        }])
        X = build_features(df)
        self.assertEqual(len(X), 1)
        self.assertIn('rating', X.columns)
        self.assertIn('platform_amazon', X.columns)
        self.assertIn('category_electronics', X.columns)
        self.assertEqual(X.iloc[0]['platform_amazon'], 1.0)
        self.assertEqual(X.iloc[0]['platform_flipkart'], 0.0)

    def test_split_reproducibility(self):
        X, y = build_training_table()
        X_tr1, X_val1, y_tr1, y_val1 = split_train_val(X, y, test_size=0.2, random_state=42)
        X_tr2, X_val2, y_tr2, y_val2 = split_train_val(X, y, test_size=0.2, random_state=42)
        
        # Verify sizes
        self.assertEqual(len(X_tr1), 9)
        self.assertEqual(len(X_val1), 3)
        # Verify reproducible splits
        pd.testing.assert_frame_equal(X_tr1, X_tr2)
        pd.testing.assert_series_equal(y_tr1, y_tr2)

    def test_linear_and_poly_regression_fits(self):
        X, y = build_training_table()
        X_train, X_val, y_train, y_val = split_train_val(X, y, test_size=0.2, random_state=42)
        
        # Train Linear
        lin_model = train_linear_model(X_train, y_train)
        self.assertTrue((get_artifacts_dir() / 'price_model_linear.joblib').exists())
        
        # Train Poly
        poly_model = train_polynomial_model(X_train, y_train, degree=2)
        self.assertTrue((get_artifacts_dir() / 'price_model_poly.joblib').exists())
        
        # Evaluate
        lin_metrics = evaluate(lin_model, X_val, y_val)
        self.assertIn('mae', lin_metrics)
        self.assertIn('r2', lin_metrics)

        # Clean up
        if (get_artifacts_dir() / 'price_model_linear.joblib').exists():
            os.remove(get_artifacts_dir() / 'price_model_linear.joblib')
        if (get_artifacts_dir() / 'price_model_poly.joblib').exists():
            os.remove(get_artifacts_dir() / 'price_model_poly.joblib')

    @override_settings(ML_MIN_TRAINING_ROWS=100)
    def test_command_early_exit_on_insufficient_data(self):
        out = StringIO()
        call_command('train_price_model', stdout=out)
        self.assertIn("Insufficient training data", out.getvalue())

    def test_command_success_with_sufficient_data(self):
        out = StringIO()
        call_command('train_price_model', stdout=out)
        self.assertIn("Successfully trained models", out.getvalue())
        self.assertTrue((get_artifacts_dir() / 'price_model_best.joblib').exists())

    def test_inference_service_predicts(self):
        # Trigger training to ensure best model artifact exists
        call_command('train_price_model', stdout=StringIO())
        
        dto = ProductDTO(
            title='Test Item',
            price=Decimal('50.00'),
            price_str='$50.00',
            product_url='https://example.com/test',
            platform='amazon',
            rating='4.0',
            raw_payload={'review_count': 50}
        )
        
        pred = predict_fair_price(dto)
        self.assertIsNotNone(pred)
        self.assertIsInstance(pred, Decimal)
        self.assertTrue(pred > 0)

    def test_inference_service_fallback_when_no_model(self):
        # Remove best model artifact if exists
        best_path = get_artifacts_dir() / 'price_model_best.joblib'
        if best_path.exists():
            os.remove(best_path)
            
        dto = ProductDTO(
            title='Test Item',
            price=Decimal('50.00'),
            price_str='$50.00',
            product_url='https://example.com/test',
            platform='amazon',
            rating='4.0'
        )
        pred = predict_fair_price(dto)
        self.assertIsNone(pred)

    def test_view_fallback_branching(self):
        # 1. No model artifact present (ml_backed=False)
        best_path = get_artifacts_dir() / 'price_model_best.joblib'
        if best_path.exists():
            os.remove(best_path)
            
        response = self.client.get(reverse('products:recommendations', kwargs={'search_id': self.sq.id}))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.context['ml_backed'])
        self.assertContains(response, "ranked by price")

        # 2. Model artifact present (ml_backed=True)
        call_command('train_price_model', stdout=StringIO())
        response = self.client.get(reverse('products:recommendations', kwargs={'search_id': self.sq.id}))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context['ml_backed'])
        self.assertContains(response, "Estimated Fair Price")

    def tearDown(self):
        artifacts = ['price_model_linear.joblib', 'price_model_poly.joblib', 'price_model_best.joblib', 'metrics.json', 'metrics_summary.json']
        for art in artifacts:
            path = get_artifacts_dir() / art
            if path.exists():
                try:
                    os.remove(path)
                except Exception:
                    pass


# ---------------------------------------------------------------------------
# Phase 14: Deal Quality Classification Tests
# ---------------------------------------------------------------------------

class DealLabelTests(TestCase):
    """Tests for ml/labels.py — label generation logic."""

    def _make_df(self, prices, search_ids=None):
        """Helper: create a minimal DataFrame for assign_deal_labels."""
        n = len(prices)
        data = {
            'price': prices,
            'search_id': search_ids if search_ids else [1] * n,
        }
        return pd.DataFrame(data)

    def test_great_deal_label(self):
        """A price far below median should be 'great_deal'."""
        # median = 100; great_deal threshold = 100 * 0.85 = 85
        df = self._make_df([50.0, 100.0, 100.0, 100.0], search_ids=[1, 1, 1, 1])
        labels = assign_deal_labels(df)
        self.assertEqual(labels.iloc[0], 'great_deal')

    def test_overpriced_label(self):
        """A price far above median should be 'overpriced'."""
        # median = 100; overpriced threshold = 100 * 1.15 = 115
        df = self._make_df([100.0, 100.0, 100.0, 200.0], search_ids=[1, 1, 1, 1])
        labels = assign_deal_labels(df)
        self.assertEqual(labels.iloc[3], 'overpriced')

    def test_fair_deal_label(self):
        """A price close to the median should be 'fair_deal'."""
        # median = 100; 100 is exactly at median → fair_deal
        df = self._make_df([100.0, 100.0, 100.0, 100.0], search_ids=[1, 1, 1, 1])
        labels = assign_deal_labels(df)
        self.assertTrue((labels == 'fair_deal').all())

    def test_nan_price_yields_nan_label(self):
        """Rows with NaN prices should receive NaN labels, not crash."""
        df = self._make_df([None, 100.0, 100.0])
        labels = assign_deal_labels(df)
        self.assertTrue(pd.isna(labels.iloc[0]))

    def test_per_search_group_labeling(self):
        """Labels should be relative to each search group's median."""
        # Group 1: prices [10, 100, 1000] → median=100
        # Group 2: prices [1, 10, 100]    → median=10
        df = pd.DataFrame({
            'price':     [10.0,  100.0, 1000.0, 1.0, 10.0, 100.0],
            'search_id': [1,     1,     1,      2,   2,    2],
        })
        labels = assign_deal_labels(df)
        # In group 1: 10 is 10% of median=100 → great_deal (≤85%)
        self.assertEqual(labels.iloc[0], 'great_deal')
        # In group 2: 100 is 10x median=10 → overpriced (>115%)
        self.assertEqual(labels.iloc[5], 'overpriced')

    def test_label_set_coverage(self):
        """All three labels should be representable."""
        df = self._make_df([50.0, 100.0, 200.0], search_ids=[1, 1, 1])
        labels = assign_deal_labels(df)
        label_set = set(labels.dropna())
        self.assertIn('great_deal', label_set)
        self.assertIn('overpriced', label_set)


class DealClassificationModelTests(TestCase):
    """Tests for ml/models.py classification functions."""

    def _make_training_data(self, n=30):
        """Create a minimal synthetic (X, y) for classifier training."""
        from ml.features import PLATFORMS, CATEGORIES

        rng = np.random.default_rng(42)
        rows = []
        labels = []
        label_cycle = ['great_deal', 'fair_deal', 'overpriced']
        for i in range(n):
            rows.append({
                'rating':       rng.uniform(1.0, 5.0),
                'review_count': rng.integers(0, 500),
                **{f'platform_{p}': 1.0 if j == (i % len(PLATFORMS)) else 0.0
                   for j, p in enumerate(PLATFORMS)},
                **{f'category_{c}': 1.0 if j == (i % len(CATEGORIES)) else 0.0
                   for j, c in enumerate(CATEGORIES)},
            })
            labels.append(label_cycle[i % 3])
        X = pd.DataFrame(rows)
        y = pd.Series(labels)
        return X, y

    def test_random_forest_trains_and_predicts(self):
        X, y = self._make_training_data()
        X_train, X_val, y_train, y_val = split_train_val(X, y, test_size=0.2, random_state=42)
        model = train_random_forest_classifier(X_train, y_train, n_estimators=10)
        self.assertTrue((get_artifacts_dir() / 'deal_model_rf.joblib').exists())

        preds = model.predict(X_val)
        self.assertEqual(len(preds), len(y_val))
        # All predictions should be in the valid label set
        for p in preds:
            self.assertIn(p, ['great_deal', 'fair_deal', 'overpriced'])

    def test_logistic_regression_trains_and_predicts(self):
        X, y = self._make_training_data()
        X_train, X_val, y_train, y_val = split_train_val(X, y, test_size=0.2, random_state=42)
        model = train_logistic_regression_classifier(X_train, y_train)
        self.assertTrue((get_artifacts_dir() / 'deal_model_lr.joblib').exists())

        preds = model.predict(X_val)
        self.assertEqual(len(preds), len(y_val))

    def test_evaluate_classifier_keys(self):
        X, y = self._make_training_data()
        X_train, X_val, y_train, y_val = split_train_val(X, y, test_size=0.2, random_state=42)
        model = train_random_forest_classifier(X_train, y_train, n_estimators=10)
        metrics = evaluate_classifier(model, X_val, y_val)
        self.assertIn('accuracy', metrics)
        self.assertIn('f1_macro', metrics)
        self.assertIn('report', metrics)
        self.assertGreaterEqual(metrics['accuracy'], 0.0)
        self.assertLessEqual(metrics['accuracy'], 1.0)

    def test_compare_classifiers_returns_both(self):
        X, y = self._make_training_data()
        X_train, X_val, y_train, y_val = split_train_val(X, y, test_size=0.2, random_state=42)
        rf = train_random_forest_classifier(X_train, y_train, n_estimators=10)
        lr = train_logistic_regression_classifier(X_train, y_train)
        comparison = compare_classifiers({'rf': rf, 'lr': lr}, X_val, y_val)
        self.assertIn('rf', comparison)
        self.assertIn('lr', comparison)

    def tearDown(self):
        for fname in ['deal_model_rf.joblib', 'deal_model_lr.joblib', 'deal_model_best.joblib', 'deal_metrics.json']:
            p = get_artifacts_dir() / fname
            if p.exists():
                try:
                    os.remove(p)
                except Exception:
                    pass


class DealManagementCommandTests(TestCase):
    """Tests for train_deal_model management command."""

    def setUp(self):
        sq = make_search_query()
        # Seed enough rows (>= 10) with varied prices to get all 3 labels
        prices = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 300.0, 500.0, 600.0, 700.0]
        for i, p in enumerate(prices):
            make_product_result(
                sq,
                price=str(p),
                rating='4.0',
                platform='amazon',
                product_url=f'https://site.com/deal/{i}',
                category='electronics',
            )

    @override_settings(ML_MIN_TRAINING_ROWS=100)
    def test_command_early_exit_insufficient_data(self):
        out = StringIO()
        call_command('train_deal_model', stdout=out)
        self.assertIn("Not enough training data", out.getvalue())
        self.assertFalse((get_artifacts_dir() / 'deal_model_best.joblib').exists())

    def test_command_trains_successfully(self):
        out = StringIO()
        call_command('train_deal_model', stdout=out)
        output = out.getvalue()
        self.assertIn("Best model", output)
        self.assertTrue((get_artifacts_dir() / 'deal_model_best.joblib').exists())
        # Metrics JSON should have been saved
        self.assertTrue((get_artifacts_dir() / 'deal_metrics.json').exists())

    def tearDown(self):
        for fname in ['deal_model_rf.joblib', 'deal_model_lr.joblib', 'deal_model_best.joblib', 'deal_metrics.json']:
            p = get_artifacts_dir() / fname
            if p.exists():
                try:
                    os.remove(p)
                except Exception:
                    pass


class DealInferenceServiceTests(TestCase):
    """Tests for predict_deal_quality() in ml/services.py."""

    def _make_dto(self, price=50.0, platform='amazon', rating='4.0'):
        return ProductDTO(
            title='Test Product',
            price=Decimal(str(price)),
            price_str=f'${price}',
            product_url='https://example.com/p',
            platform=platform,
            rating=rating,
            raw_payload={},
        )

    def test_returns_none_when_no_model(self):
        best_path = get_artifacts_dir() / 'deal_model_best.joblib'
        if best_path.exists():
            os.remove(best_path)
        result = predict_deal_quality(self._make_dto())
        self.assertIsNone(result)

    def test_returns_valid_label_when_model_present(self):
        # Train a model first
        sq = make_search_query()
        prices = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 300.0, 500.0, 600.0, 700.0]
        for i, p in enumerate(prices):
            make_product_result(sq, price=str(p), rating='4.0',
                                platform='amazon', product_url=f'https://site.com/inf/{i}',
                                category='electronics')
        call_command('train_deal_model', stdout=StringIO())

        result = predict_deal_quality(self._make_dto(price=50.0))
        self.assertIn(result, ['great_deal', 'fair_deal', 'overpriced'])

    def test_badge_map_has_all_labels(self):
        self.assertIn('great_deal', DEAL_BADGE_MAP)
        self.assertIn('fair_deal', DEAL_BADGE_MAP)
        self.assertIn('overpriced', DEAL_BADGE_MAP)

    def tearDown(self):
        for fname in ['deal_model_rf.joblib', 'deal_model_lr.joblib', 'deal_model_best.joblib', 'deal_metrics.json']:
            p = get_artifacts_dir() / fname
            if p.exists():
                try:
                    os.remove(p)
                except Exception:
                    pass


class DealQualityViewIntegrationTests(TestCase):
    """Tests that recommendations view correctly populates deal_badge context."""

    def setUp(self):
        self.sq = make_search_query()
        prices = [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 300.0, 500.0, 600.0, 700.0]
        for i, p in enumerate(prices):
            make_product_result(
                self.sq, price=str(p), rating='4.0',
                platform='amazon', product_url=f'https://site.com/view/{i}',
                category='electronics',
                raw_data={'in_stock': True},
            )

    def test_recommendations_have_deal_badge_key(self):
        """All recommendations should include 'deal_badge' key (may be empty string)."""
        response = self.client.get(
            reverse('products:recommendations', kwargs={'search_id': self.sq.id})
        )
        self.assertEqual(response.status_code, 200)
        recs = response.context['recommendations']
        self.assertGreater(len(recs), 0)
        for rec in recs:
            self.assertIn('deal_badge', rec)
            self.assertIn('deal_quality', rec)

    def test_recommendations_deal_badge_empty_without_model(self):
        """Without a trained deal model, deal_badge should be empty string."""
        best_path = get_artifacts_dir() / 'deal_model_best.joblib'
        if best_path.exists():
            os.remove(best_path)

        response = self.client.get(
            reverse('products:recommendations', kwargs={'search_id': self.sq.id})
        )
        recs = response.context['recommendations']
        for rec in recs:
            self.assertEqual(rec['deal_badge'], '')
            self.assertIsNone(rec['deal_quality'])

    def tearDown(self):
        for fname in ['deal_model_rf.joblib', 'deal_model_lr.joblib', 'deal_model_best.joblib',
                      'deal_metrics.json', 'price_model_best.joblib', 'metrics.json']:
            p = get_artifacts_dir() / fname
            if p.exists():
                try:
                    os.remove(p)
                except Exception:
                    pass

