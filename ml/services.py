import joblib
from pathlib import Path
from decimal import Decimal
import pandas as pd
from django.conf import settings
from ml.features import build_features
from ml.models import get_artifacts_dir

def predict_fair_price(product_dto) -> Decimal | None:
    artifacts_dir = get_artifacts_dir()
    best_path = artifacts_dir / 'price_model_best.joblib'
    
    if not best_path.exists():
        return None

    try:
        model = joblib.load(best_path)
    except Exception:
        return None

    review_count = getattr(product_dto, 'review_count', None)
    if review_count is None:
        raw = getattr(product_dto, 'raw_payload', {}) or {}
        review_count = raw.get('reviews') or raw.get('review_count')

    df_single = pd.DataFrame([{
        'platform': getattr(product_dto, 'platform', 'unknown') or 'unknown',
        'category': getattr(product_dto, 'category', 'unknown') or 'unknown',
        'rating': getattr(product_dto, 'rating', None),
        'review_count': review_count,
        'raw_payload': getattr(product_dto, 'raw_payload', {})
    }])

    # Build features
    X_single = build_features(df_single)

    try:
        pred = model.predict(X_single)[0]
        # Coerce prediction value to non-negative float
        pred = max(0.0, float(pred))
        return Decimal(f"{pred:.2f}")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Phase 14: Deal Quality Classification Inference
# ---------------------------------------------------------------------------

#: Canonical label set returned by the classifier
DEAL_LABEL_GREAT = 'great_deal'
DEAL_LABEL_FAIR  = 'fair_deal'
DEAL_LABEL_OVER  = 'overpriced'
VALID_DEAL_LABELS = {DEAL_LABEL_GREAT, DEAL_LABEL_FAIR, DEAL_LABEL_OVER}

#: Human-readable badges shown in the template
DEAL_BADGE_MAP = {
    DEAL_LABEL_GREAT: '🟢 Great Deal',
    DEAL_LABEL_FAIR:  '🟡 Fair Deal',
    DEAL_LABEL_OVER:  '🔴 Overpriced',
}


def predict_deal_quality(product_dto) -> str | None:
    """
    Predict the deal-quality label for a single product.

    Returns one of: 'great_deal', 'fair_deal', 'overpriced'.
    Returns None if the classification model artifact does not exist or
    an error occurs during inference (safe fallback).

    Parameters
    ----------
    product_dto : ProductDTO (or any object with title, price, platform,
                  category, rating, raw_payload attributes)
    """
    artifacts_dir = get_artifacts_dir()
    model_path = artifacts_dir / 'deal_model_best.joblib'

    if not model_path.exists():
        return None

    try:
        model = joblib.load(model_path)
    except Exception:
        return None

    review_count = getattr(product_dto, 'review_count', None)
    if review_count is None:
        raw = getattr(product_dto, 'raw_payload', {}) or {}
        review_count = raw.get('reviews') or raw.get('review_count')

    df_single = pd.DataFrame([{
        'platform':     getattr(product_dto, 'platform', 'unknown') or 'unknown',
        'category':     getattr(product_dto, 'category', 'unknown') or 'unknown',
        'rating':       getattr(product_dto, 'rating', None),
        'review_count': review_count,
        'raw_payload':  getattr(product_dto, 'raw_payload', {}),
    }])

    X_single = build_features(df_single)

    try:
        label = model.predict(X_single)[0]
        # Guard against unexpected / corrupted model output
        if label not in VALID_DEAL_LABELS:
            return None
        return label
    except Exception:
        return None
