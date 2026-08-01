import time
import logging
from functools import wraps
from django.http import JsonResponse, Http404
from django.contrib.auth.decorators import login_required
from django.core.cache import cache
from analytics.models import AnalyticsSnapshot
from analytics.loaders import load_results_df, clean_df
from analytics.utils import build_plotly_figure

logger = logging.getLogger('endpoints')

def throttle_session(limit=60, period=60):
    """Simple per-session cache-based rate limiting."""
    def decorator(view_func):
        @wraps(view_func)
        def _wrapped_view(request, *args, **kwargs):
            if not request.session.session_key:
                request.session.create()
            session_key = request.session.session_key
            
            now = int(time.time())
            window = now // period
            key = f"throttle:{session_key}:{window}"
            
            count = cache.get(key, 0)
            if count >= limit:
                response = JsonResponse({"error": "Too Many Requests. Rate limit exceeded."}, status=429)
                response['Retry-After'] = str(period - (now % period))
                return response
            
            cache.set(key, count + 1, period)
            return view_func(request, *args, **kwargs)
        return _wrapped_view
    return decorator

@login_required(login_url='/accounts/login/')
@throttle_session(limit=60, period=60)
def analytics_summary_json(request):
    """GET /endpoints/analytics/summary.json -> serializes latest AnalyticsSnapshot."""
    snapshot = AnalyticsSnapshot.latest()
    if not snapshot:
        return JsonResponse({"status": "not computed yet", "message": "No analytics snapshot exists yet."}, status=200)
    return JsonResponse(snapshot.data)

@login_required(login_url='/accounts/login/')
@throttle_session(limit=60, period=60)
def analytics_chart_json(request, name):
    """GET /endpoints/analytics/chart/<name>.json -> returns Plotly figure data."""
    if name not in ['histogram', 'boxplot', 'scatter']:
        return JsonResponse({"error": f"Chart name '{name}' is not supported. Supported: histogram, boxplot, scatter."}, status=404)
        
    df = load_results_df()
    clean = clean_df(df)
    
    platform = request.GET.get('platform', '').strip().lower()
    if platform and platform != 'all' and not clean.empty:
        clean = clean[clean['platform'].str.lower() == platform]
        
    plotly_fig = build_plotly_figure(name, clean)
    return JsonResponse(plotly_fig)
