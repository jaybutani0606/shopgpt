"""
ml/labels.py
~~~~~~~~~~~~
Generates "deal quality" classification labels for product listings.

Labels are assigned by comparing each product's price against the median
price within its search-query group:

    - "great_deal"  : price <= median * 0.85   (at least 15% below median)
    - "fair_deal"   : median * 0.85 < price <= median * 1.15
    - "overpriced"  : price > median * 1.15     (more than 15% above median)

These thresholds mirror real-world "good deal" heuristics and give balanced
enough class distribution for a small-to-medium training corpus.
"""

import numpy as np
import pandas as pd

# Configurable thresholds (can be overridden in tests or settings)
GREAT_DEAL_THRESHOLD = 0.85   # great deal
OVERPRICED_THRESHOLD = 1.15   # overpriced


def assign_deal_labels(df: pd.DataFrame) -> pd.Series:
    """
    Assign a deal-quality label to every row in *df*.

    The DataFrame must contain at least:
        - 'price'     (numeric)
        - 'search_id' (int/str, used to group products within the same search)

    Returns a pd.Series of strings: 'great_deal', 'fair_deal', 'overpriced'.
    Rows whose price is NaN receive NaN labels.
    """
    prices = pd.to_numeric(df['price'], errors='coerce')

    # Compute per-search-group median, fall back to global median if a group
    # has only 1 member (median == price → everything is "fair")
    if 'search_id' in df.columns and df['search_id'].nunique() > 1:
        median_by_search = prices.groupby(df['search_id']).transform('median')
    else:
        # Single group or no search_id column — use the global median
        median_by_search = pd.Series(prices.median(), index=df.index)

    labels = pd.Series(index=df.index, dtype=object)

    great_mask = prices <= (median_by_search * GREAT_DEAL_THRESHOLD)
    over_mask  = prices >  (median_by_search * OVERPRICED_THRESHOLD)
    fair_mask  = ~great_mask & ~over_mask

    labels[great_mask] = 'great_deal'
    labels[fair_mask]  = 'fair_deal'
    labels[over_mask]  = 'overpriced'

    # Preserve NaN for rows where price could not be parsed
    labels[prices.isna()] = np.nan

    return labels


def build_deal_training_table():
    """
    Load all ProductResult rows, clean them, and return (X, y) for
    classification where y contains deal-quality string labels.

    Uses the shared feature matrix from ml.features.build_features().
    """
    from analytics.loaders import load_results_df, clean_df
    from ml.features import build_features

    df = load_results_df()
    clean = clean_df(df)

    if clean.empty:
        X = build_features(clean)
        y = pd.Series(dtype=object)
        return X, y

    # Attach search_id for per-group median computation
    if 'search_id' not in clean.columns:
        clean = clean.copy()
        clean['search_id'] = 0   # treat everything as one group

    labels = assign_deal_labels(clean)

    # Drop rows where we couldn't derive a label (NaN price after cleaning)
    valid = labels.notna()
    X = build_features(clean[valid])
    y = labels[valid].reset_index(drop=True)
    return X, y
