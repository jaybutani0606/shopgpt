import pandas as pd
import numpy as np
from analytics.loaders import load_results_df, clean_df

PLATFORMS = ['amazon', 'flipkart', 'croma', 'reliance']
CATEGORIES = ['electronics', 'fashion', 'home', 'unknown']

def build_features(df):
    if df.empty:
        cols = ['rating', 'review_count']
        for plat in PLATFORMS:
            cols.append(f'platform_{plat}')
        for cat in CATEGORIES:
            cols.append(f'category_{cat}')
        return pd.DataFrame(columns=cols)

    ratings = pd.to_numeric(df['rating'], errors='coerce').fillna(0.0)
    reviews = pd.to_numeric(df['review_count'], errors='coerce').fillna(0.0)
    
    platform_features = {}
    for plat in PLATFORMS:
        platform_features[f'platform_{plat}'] = (df['platform'] == plat).astype(float)
        
    category_features = {}
    for cat in CATEGORIES:
        category_features[f'category_{cat}'] = (df['category'] == cat).astype(float)
        
    X_dict = {
        'rating': ratings.astype(float),
        'review_count': reviews.astype(float),
        **platform_features,
        **category_features
    }
    # Return DataFrame with consistent column order
    cols = ['rating', 'review_count']
    for plat in PLATFORMS:
        cols.append(f'platform_{plat}')
    for cat in CATEGORIES:
        cols.append(f'category_{cat}')
        
    return pd.DataFrame(X_dict)[cols]

def build_training_table():
    df = load_results_df()
    clean = clean_df(df)
    if clean.empty:
        return build_features(clean), pd.Series(dtype=float)
    X = build_features(clean)
    y = clean['price'].astype(float)
    return X, y
