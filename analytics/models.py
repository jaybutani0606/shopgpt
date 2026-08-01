from django.db import models
from django.utils import timezone
import math

def sanitize_json_data(data):
    if isinstance(data, dict):
        return {k: sanitize_json_data(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [sanitize_json_data(v) for v in data]
    elif isinstance(data, float):
        if math.isnan(data) or math.isinf(data):
            return None
    return data

class AnalyticsSnapshot(models.Model):
    created_at = models.DateTimeField(default=timezone.now)
    data = models.JSONField()

    class Meta:
        ordering = ['-created_at']

    @classmethod
    def create_from(cls, df):
        from analytics.analysis import aggregate_by_platform, value_counts_by_platform, describe_prices, correlation_matrix
        
        aggs = aggregate_by_platform(df)
        aggs_dict = aggs.to_dict(orient='index') if not aggs.empty else {}
        
        counts = value_counts_by_platform(df)
        counts_dict = counts.to_dict() if not counts.empty else {}
        
        desc = describe_prices(df)
        desc_dict = desc.to_dict() if not desc.empty else {}
        
        corr = correlation_matrix(df)
        corr_dict = corr.to_dict(orient='index') if not corr.empty else {}
        
        snapshot_data = {
            'aggregations': aggs_dict,
            'value_counts': counts_dict,
            'describe': desc_dict,
            'correlation': corr_dict
        }
        sanitized_data = sanitize_json_data(snapshot_data)
        return cls.objects.create(data=sanitized_data)

    @classmethod
    def latest(cls):
        return cls.objects.order_by('-created_at').first()
