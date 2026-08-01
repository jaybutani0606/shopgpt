import pandas as pd
from products.models import ProductResult

def load_results_df(queryset=None):
    if queryset is None:
        queryset = ProductResult.objects.all()
    values_list = list(queryset.values(
        'id', 'platform', 'title', 'price', 'product_url', 'rating', 'raw_data', 'category'
    ))
    if not values_list:
        return pd.DataFrame(columns=['id', 'platform', 'title', 'price', 'product_url', 'rating', 'raw_data', 'category', 'review_count'])
        
    df = pd.DataFrame(values_list)
    if 'price' in df.columns:
        df['price'] = pd.to_numeric(df['price'], errors='coerce')
    return df

def clean_df(df):
    if df.empty:
        return df.copy()
        
    # Drop rows missing price
    df = df.dropna(subset=['price']).copy()
    
    # Drop duplicate items sharing platform and URL
    df = df.drop_duplicates(subset=['platform', 'product_url']).copy()
    
    # Parse review_count from raw_data if not present
    if 'review_count' not in df.columns:
        def get_reviews(raw):
            if isinstance(raw, dict):
                return raw.get('reviews') or raw.get('review_count')
            return None
        df['review_count'] = df['raw_data'].apply(get_reviews)
        
    # Fill rating sentinel
    df['rating'] = df['rating'].fillna('unknown')
    
    # Fill review_count sentinel
    df['review_count'] = pd.to_numeric(df['review_count'], errors='coerce').fillna(-1).astype(int)
    
    return df
