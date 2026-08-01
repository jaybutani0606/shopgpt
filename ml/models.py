import json
import joblib
from pathlib import Path
from django.conf import settings
from sklearn.model_selection import train_test_split
from sklearn.linear_model import LinearRegression, LogisticRegression
from sklearn.ensemble import RandomForestClassifier
from sklearn.preprocessing import PolynomialFeatures, LabelEncoder
from sklearn.pipeline import make_pipeline
from sklearn.metrics import (
    mean_absolute_error, mean_squared_error, r2_score,
    accuracy_score, f1_score, classification_report
)

def split_train_val(X, y, test_size=0.2, random_state=42):
    return train_test_split(X, y, test_size=test_size, random_state=random_state)

def get_artifacts_dir():
    artifacts_dir = Path(getattr(settings, 'ML_ARTIFACTS_DIR', Path(settings.BASE_DIR) / 'ml' / 'artifacts'))
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    return artifacts_dir

def train_linear_model(X_train, y_train):
    model = LinearRegression()
    model.fit(X_train, y_train)
    artifacts_dir = get_artifacts_dir()
    filepath = artifacts_dir / 'price_model_linear.joblib'
    joblib.dump(model, filepath)
    return model

def train_polynomial_model(X_train, y_train, degree=2):
    model = make_pipeline(PolynomialFeatures(degree=degree), LinearRegression())
    model.fit(X_train, y_train)
    artifacts_dir = get_artifacts_dir()
    filepath = artifacts_dir / 'price_model_poly.joblib'
    joblib.dump(model, filepath)
    return model

def evaluate(model, X_val, y_val):
    predictions = model.predict(X_val)
    mae = mean_absolute_error(y_val, predictions)
    mse = mean_squared_error(y_val, predictions)
    r2 = r2_score(y_val, predictions)
    
    metrics = {
        'mae': float(mae),
        'mse': float(mse),
        'r2': float(r2)
    }
    return metrics

def save_metrics(metrics, filename='metrics.json'):
    artifacts_dir = get_artifacts_dir()
    filepath = artifacts_dir / filename
    with open(filepath, 'w') as f:
        json.dump(metrics, f, indent=4)

def compare_models(models_dict, X_val, y_val):
    comparison = {}
    for name, model in models_dict.items():
        comparison[name] = evaluate(model, X_val, y_val)
    return comparison

# ---------------------------------------------------------------------------
# Phase 14: Classification — Deal Quality Model
# ---------------------------------------------------------------------------

DEAL_LABELS = ['great_deal', 'fair_deal', 'overpriced']


def train_random_forest_classifier(X_train, y_train, n_estimators=100, random_state=42):
    """
    Train a RandomForestClassifier on the deal-quality labels.
    Saves artifact to ml/artifacts/deal_model_rf.joblib.
    Returns the fitted model.
    """
    model = RandomForestClassifier(
        n_estimators=n_estimators,
        random_state=random_state,
        class_weight='balanced',   # handles class imbalance gracefully
    )
    model.fit(X_train, y_train)
    artifacts_dir = get_artifacts_dir()
    joblib.dump(model, artifacts_dir / 'deal_model_rf.joblib')
    return model


def train_logistic_regression_classifier(X_train, y_train, random_state=42):
    """
    Train a multi-class LogisticRegression on the deal-quality labels.
    Saves artifact to ml/artifacts/deal_model_lr.joblib.
    Returns the fitted model.
    """
    model = LogisticRegression(
        max_iter=1000,
        random_state=random_state,
        class_weight='balanced',
        solver='lbfgs',
    )
    model.fit(X_train, y_train)
    artifacts_dir = get_artifacts_dir()
    joblib.dump(model, artifacts_dir / 'deal_model_lr.joblib')
    return model


def evaluate_classifier(model, X_val, y_val):
    """
    Evaluate a classification model.
    Returns a dict with accuracy, macro-F1, and a per-class report.
    """
    predictions = model.predict(X_val)
    acc = accuracy_score(y_val, predictions)
    f1  = f1_score(y_val, predictions, average='macro', zero_division=0)
    report = classification_report(
        y_val, predictions,
        labels=DEAL_LABELS,
        zero_division=0,
        output_dict=True,
    )
    return {
        'accuracy': float(acc),
        'f1_macro': float(f1),
        'report': report,
    }


def compare_classifiers(models_dict, X_val, y_val):
    """
    Compare multiple classification models.
    Returns a dict of {model_name: evaluation_metrics}.
    """
    return {name: evaluate_classifier(m, X_val, y_val) for name, m in models_dict.items()}
