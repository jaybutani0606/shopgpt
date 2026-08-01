from django.urls import path
from products.views import (
    SearchView,
    ResultsView,
    ComparisonView,
    TopRecommendationsView,
    HistoryView
)

app_name = 'products'

urlpatterns = [
    path('search/', SearchView.as_view(), name='search'),
    path('results/<int:search_id>/', ResultsView.as_view(), name='results'),
    path('compare/<int:search_id>/', ComparisonView.as_view(), name='compare'),
    path('recommendations/<int:search_id>/', TopRecommendationsView.as_view(), name='recommendations'),
    path('history/', HistoryView.as_view(), name='history'),
]
