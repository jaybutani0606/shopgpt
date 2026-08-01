from django.urls import path
from .views import analytics_summary_json, analytics_chart_json

app_name = 'endpoints'

urlpatterns = [
    path('analytics/summary.json', analytics_summary_json, name='analytics_summary'),
    path('analytics/chart/<str:name>.json', analytics_chart_json, name='analytics_chart'),
]
