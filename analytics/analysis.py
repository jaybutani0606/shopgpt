import pandas as pd
import numpy as np

def aggregate_by_platform(df):
    if df.empty or 'price' not in df.columns:
        return pd.DataFrame(columns=['mean', 'median', 'count'])
    return df.groupby('platform')['price'].agg(['mean', 'median', 'count'])

def value_counts_by_platform(df):
    if df.empty or 'platform' not in df.columns:
        return pd.Series(dtype=int)
    return df['platform'].value_counts()

def describe_prices(df):
    if df.empty or 'price' not in df.columns:
        return pd.Series(dtype=float)
    return df['price'].describe()

def filter_by_price_range(df, low, high):
    if df.empty or 'price' not in df.columns:
        return df.copy()
    return df[(df['price'] >= low) & (df['price'] <= high)].copy()

def correlation_matrix(df):
    if df.empty:
        return pd.DataFrame()
        
    # Coerce price, rating, review_count to numeric
    rating_numeric = pd.to_numeric(df['rating'], errors='coerce')
    price_numeric = pd.to_numeric(df['price'], errors='coerce')
    reviews_numeric = pd.to_numeric(df['review_count'], errors='coerce')
    
    analysis_df = pd.DataFrame({
        'price': price_numeric,
        'rating': rating_numeric,
        'review_count': reviews_numeric
    })
    return analysis_df.corr()

def detect_price_outliers(df):
    if df.empty or 'price' not in df.columns:
        return df.copy()
        
    outliers = []
    for platform, group in df.groupby('platform'):
        prices = group['price'].dropna()
        if len(prices) < 4:
            continue
        q1 = prices.quantile(0.25)
        q3 = prices.quantile(0.75)
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        group_outliers = group[(group['price'] < lower_bound) | (group['price'] > upper_bound)]
        outliers.append(group_outliers)
        
    if not outliers:
        return pd.DataFrame(columns=df.columns)
        
    return pd.concat(outliers)
