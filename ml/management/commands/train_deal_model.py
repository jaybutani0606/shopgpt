"""
ml/management/commands/train_deal_model.py
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~
Management command that trains the "Deal Quality" classification model.

Usage:
    python manage.py train_deal_model

The command:
1. Loads all ProductResult rows and derives deal-quality labels.
2. Verifies there are at least ML_MIN_TRAINING_ROWS rows (default: 10).
3. Splits into train/validation sets (80/20).
4. Trains both a Random Forest classifier and a Logistic Regression.
5. Compares the two on the validation split (by macro-F1).
6. Saves the best model to ml/artifacts/deal_model_best.joblib.
7. Persists full metrics to ml/artifacts/deal_metrics.json.
"""

import json
import logging
import joblib

from django.conf import settings
from django.core.management.base import BaseCommand

from ml.labels import build_deal_training_table
from ml.models import (
    get_artifacts_dir,
    split_train_val,
    save_metrics,
    train_random_forest_classifier,
    train_logistic_regression_classifier,
    compare_classifiers,
)

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = 'Train the deal-quality classification model (Random Forest vs Logistic Regression).'

    def handle(self, *args, **options):
        min_rows = getattr(settings, 'ML_MIN_TRAINING_ROWS', 10)
        self.stdout.write('Loading deal-quality training data …')
        X, y = build_deal_training_table()

        if len(X) < min_rows:
            self.stdout.write(
                self.style.WARNING(
                    f'Not enough training data: found {len(X)} rows, need {min_rows}. '
                    'Skipping training — existing model (if any) is unchanged.'
                )
            )
            logger.warning(
                'train_deal_model: insufficient data (%d rows, minimum %d). Aborted.',
                len(X), min_rows,
            )
            return

        self.stdout.write(f'Training on {len(X)} rows with labels: {sorted(y.unique())}')

        X_train, X_val, y_train, y_val = split_train_val(X, y)

        # Train both models
        self.stdout.write('Training Random Forest classifier …')
        rf_model = train_random_forest_classifier(X_train, y_train)

        self.stdout.write('Training Logistic Regression classifier …')
        lr_model = train_logistic_regression_classifier(X_train, y_train)

        # Evaluate
        comparison = compare_classifiers(
            {'random_forest': rf_model, 'logistic_regression': lr_model},
            X_val, y_val,
        )

        # Select the model with the highest macro-F1
        best_name = max(comparison, key=lambda k: comparison[k]['f1_macro'])
        best_model = rf_model if best_name == 'random_forest' else lr_model

        artifacts_dir = get_artifacts_dir()
        best_path = artifacts_dir / 'deal_model_best.joblib'
        joblib.dump(best_model, best_path)

        # Log summary
        for name, metrics in comparison.items():
            self.stdout.write(
                f'  {name}: accuracy={metrics["accuracy"]:.3f}, '
                f'f1_macro={metrics["f1_macro"]:.3f}'
            )
            logger.info('deal model [%s]: %s', name, metrics)

        self.stdout.write(
            self.style.SUCCESS(
                f'Best model: {best_name} (f1_macro={comparison[best_name]["f1_macro"]:.3f}). '
                f'Saved to {best_path}'
            )
        )

        # Save full comparison metrics
        save_metrics(comparison, filename='deal_metrics.json')
        logger.info('deal_model trained. Best: %s', best_name)
