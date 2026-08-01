from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView
from django.db.models import Avg, Min, Max, Count
from django.conf import settings
from products.models import ProductResult, SearchQuery
import json


class AnalyticsDashboardView(LoginRequiredMixin, TemplateView):
    """Analytics dashboard showing price distribution, platform stats and deal insights."""

    template_name = 'analytics/dashboard.html'
    login_url = '/accounts/login/'

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)

        # ── Overall stats ──────────────────────────────────────────
        total_searches = SearchQuery.objects.filter(user=self.request.user).count()
        total_results  = ProductResult.objects.filter(
            search__user=self.request.user
        ).count()

        # ── Platform breakdown ─────────────────────────────────────
        platform_qs = (
            ProductResult.objects
            .filter(search__user=self.request.user, price__isnull=False)
            .values('platform')
            .annotate(
                count=Count('id'),
                avg_price=Avg('price'),
                min_price=Min('price'),
                max_price=Max('price'),
            )
            .order_by('-count')
        )

        platforms = []
        chart_labels = []
        chart_counts = []
        chart_avg_prices = []

        for row in platform_qs:
            label = row['platform'].capitalize()
            platforms.append({
                'name':      label,
                'count':     row['count'],
                'avg_price': round(float(row['avg_price']), 2) if row['avg_price'] else 0,
                'min_price': round(float(row['min_price']), 2) if row['min_price'] else 0,
                'max_price': round(float(row['max_price']), 2) if row['max_price'] else 0,
            })
            chart_labels.append(label)
            chart_counts.append(row['count'])
            chart_avg_prices.append(round(float(row['avg_price']), 2) if row['avg_price'] else 0)

        # ── Price histogram data ────────────────────────────────────
        price_qs = (
            ProductResult.objects
            .filter(search__user=self.request.user, price__isnull=False)
            .values_list('price', flat=True)
        )
        prices = [float(p) for p in price_qs]

        # Build 10-bucket histogram
        hist_labels, hist_counts = self._build_histogram(prices, buckets=10)

        # ── Recent searches ────────────────────────────────────────
        recent = (
            SearchQuery.objects
            .filter(user=self.request.user, status='completed')
            .order_by('-timestamp')[:8]
        )

        # ── Model Metrics Panel ────────────────────────────────────
        from pathlib import Path
        ml_artifacts_dir = Path(settings.BASE_DIR) / 'ml' / 'artifacts'
        price_metrics_path = ml_artifacts_dir / 'metrics.json'
        deal_metrics_path = ml_artifacts_dir / 'metrics_classification.json'
        
        price_metrics = None
        if price_metrics_path.exists():
            try:
                with open(price_metrics_path, 'r') as f:
                    price_metrics = json.load(f)
            except Exception:
                pass
                
        deal_metrics = None
        if deal_metrics_path.exists():
            try:
                with open(deal_metrics_path, 'r') as f:
                    deal_metrics = json.load(f)
            except Exception:
                pass

        ctx.update({
            'total_searches':    total_searches,
            'total_results':     total_results,
            'platforms':         platforms,
            'chart_labels_json': json.dumps(chart_labels),
            'chart_counts_json': json.dumps(chart_counts),
            'chart_avg_json':    json.dumps(chart_avg_prices),
            'hist_labels_json':  json.dumps(hist_labels),
            'hist_counts_json':  json.dumps(hist_counts),
            'recent_searches':   recent,
            'price_metrics':     price_metrics,
            'deal_metrics':      deal_metrics,
        })
        return ctx

    @staticmethod
    def _build_histogram(values, buckets=10):
        if not values:
            return [], []
        mn, mx = min(values), max(values)
        if mn == mx:
            return [f'₹{mn:.0f}'], [len(values)]
        step = (mx - mn) / buckets
        labels, counts = [], []
        for i in range(buckets):
            lo = mn + i * step
            hi = lo + step
            cnt = sum(1 for v in values if lo <= v < hi)
            labels.append(f'₹{lo:,.0f}–{hi:,.0f}')
            counts.append(cnt)
        return labels, counts
