import os
import time
import re
from pathlib import Path
from decimal import Decimal
import numpy as np
import pandas as pd
from django.conf import settings

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import seaborn as sns

def build_histogram_data(df, bins=20):
    if df.empty or 'price' not in df.columns:
        return []
    prices = df['price'].dropna()
    if len(prices) == 0:
        return []
    counts, edges = np.histogram(prices, bins=bins)
    data = []
    for i in range(len(counts)):
        data.append({
            'bin_start': float(edges[i]),
            'bin_end': float(edges[i+1]),
            'count': int(counts[i])
        })
    return data

def build_boxplot_data(df):
    if df.empty or 'price' not in df.columns:
        return {}
    data = {}
    for platform, group in df.groupby('platform'):
        prices = group['price'].dropna()
        if len(prices) == 0:
            continue
        q1 = float(prices.quantile(0.25))
        median = float(prices.median())
        q3 = float(prices.quantile(0.75))
        iqr = q3 - q1
        lower_bound = q1 - 1.5 * iqr
        upper_bound = q3 + 1.5 * iqr
        
        non_outliers = prices[(prices >= lower_bound) & (prices <= upper_bound)]
        min_val = float(non_outliers.min()) if not non_outliers.empty else float(prices.min())
        max_val = float(non_outliers.max()) if not non_outliers.empty else float(prices.max())
        
        outliers = prices[(prices < lower_bound) | (prices > upper_bound)].tolist()
        data[platform] = {
            'min': min_val,
            'q1': q1,
            'median': median,
            'q3': q3,
            'max': max_val,
            'outliers': [float(x) for x in outliers]
        }
    return data

def build_scatter_data(df):
    if df.empty or 'price' not in df.columns or 'rating' not in df.columns:
        return []
    df_copy = df.copy()
    df_copy['rating_numeric'] = pd.to_numeric(df_copy['rating'], errors='coerce')
    df_clean = df_copy.dropna(subset=['price', 'rating_numeric'])
    
    data = []
    for _, row in df_clean.iterrows():
        data.append({
            'price': float(row['price']),
            'rating': float(row['rating_numeric']),
            'platform': str(row['platform'])
        })
    return data

def export_chart_image(kind, df) -> Path:
    sns.set_theme(style="darkgrid")
    fig = plt.figure(figsize=(8, 6))
    
    if kind == 'histogram':
        if not df.empty and 'price' in df.columns:
            sns.histplot(data=df, x='price', bins=20, kde=True)
        plt.title("Price Distribution")
    elif kind == 'boxplot':
        if not df.empty and 'price' in df.columns and 'platform' in df.columns:
            sns.boxplot(data=df, x='platform', y='price')
        plt.title("Price by Platform")
    elif kind == 'scatter':
        if not df.empty and 'price' in df.columns and 'rating' in df.columns:
            df_copy = df.copy()
            df_copy['rating_numeric'] = pd.to_numeric(df_copy['rating'], errors='coerce')
            df_clean = df_copy.dropna(subset=['price', 'rating_numeric'])
            if not df_clean.empty:
                sns.scatterplot(data=df_clean, x='price', y='rating_numeric', hue='platform')
        plt.title("Price vs Rating")
    else:
        plt.plot([0, 1], [0, 1])
        plt.title("Fallback Plot")
        
    media_root = getattr(settings, 'MEDIA_ROOT', 'media')
    charts_dir = Path(media_root) / 'charts'
    charts_dir.mkdir(parents=True, exist_ok=True)
    
    filename = f"{kind}-{int(time.time())}.png"
    filepath = charts_dir / filename
    plt.savefig(filepath, format='png', bbox_inches='tight')
    plt.close(fig)
    return filepath

def build_plotly_figure(kind, df) -> dict:
    if kind == 'histogram':
        x_data = df['price'].tolist() if (not df.empty and 'price' in df.columns) else []
        return {
            'data': [{
                'x': x_data,
                'type': 'histogram',
                'name': 'Price Distribution'
            }],
            'layout': {
                'title': 'Price Distribution',
                'xaxis': {'title': 'Price'},
                'yaxis': {'title': 'Count'}
            }
        }
    elif kind == 'boxplot':
        traces = []
        if not df.empty and 'price' in df.columns and 'platform' in df.columns:
            for platform, group in df.groupby('platform'):
                traces.append({
                    'y': group['price'].tolist(),
                    'type': 'box',
                    'name': platform
                })
        return {
            'data': traces,
            'layout': {
                'title': 'Price by Platform',
                'yaxis': {'title': 'Price'}
            }
        }
    elif kind == 'scatter':
        traces = []
        if not df.empty and 'price' in df.columns and 'rating' in df.columns:
            df_copy = df.copy()
            df_copy['rating_numeric'] = pd.to_numeric(df_copy['rating'], errors='coerce')
            df_clean = df_copy.dropna(subset=['price', 'rating_numeric'])
            for platform, group in df_clean.groupby('platform'):
                traces.append({
                    'x': group['price'].tolist(),
                    'y': group['rating_numeric'].tolist(),
                    'mode': 'markers',
                    'type': 'scatter',
                    'name': platform
                })
        return {
            'data': traces,
            'layout': {
                'title': 'Price vs Rating',
                'xaxis': {'title': 'Price'},
                'yaxis': {'title': 'Rating'}
            }
        }
    return {'data': [], 'layout': {}}
