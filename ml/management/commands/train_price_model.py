import os
import joblib
from django.core.management.base import BaseCommand
from django.conf import settings
from ml.features import build_training_table
from ml.models import (
    split_train_val,
    train_linear_model,
    train_polynomial_model,
    compare_models,
    save_metrics,
    get_artifacts_dir
)

class Command(BaseCommand):
    help = 'Loads data, trains Linear and Polynomial Regression models, and saves the best model.'

    def handle(self, *args, **options):
        min_rows = getattr(settings, 'ML_MIN_TRAINING_ROWS', 10)
        X, y = build_training_table()
        
        if len(X) < min_rows:
            self.stdout.write(self.style.WARNING(
                f"Insufficient training data. Found {len(X)} rows, need at least {min_rows}."
            ))
            return

        # Train/Val Split
        X_train, X_val, y_train, y_val = split_train_val(X, y)

        # Train models
        linear_model = train_linear_model(X_train, y_train)
        poly_model = train_polynomial_model(X_train, y_train, degree=2)

        # Compare models
        models = {
            'linear': linear_model,
            'polynomial': poly_model
        }
        comparison_metrics = compare_models(models, X_val, y_val)
        save_metrics(comparison_metrics, 'metrics.json')

        # Select best model (lowest MAE)
        best_name = 'linear'
        if comparison_metrics['polynomial']['mae'] < comparison_metrics['linear']['mae']:
            best_name = 'polynomial'

        best_model = models[best_name]
        artifacts_dir = get_artifacts_dir()
        best_path = artifacts_dir / 'price_model_best.joblib'
        joblib.dump(best_model, best_path)

        # Record which model was selected as best
        info = {
            'best_model': best_name,
            'metrics': comparison_metrics
        }
        save_metrics(info, 'metrics_summary.json')

        self.stdout.write(self.style.SUCCESS(
            f"Successfully trained models. Selected '{best_name}' model as best (MAE: {comparison_metrics[best_name]['mae']:.4f})."
        ))
