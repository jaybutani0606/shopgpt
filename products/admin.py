from django.contrib import admin
from products.models import SearchQuery, ProductResult

@admin.register(SearchQuery)
class SearchQueryAdmin(admin.ModelAdmin):
    list_display = ('id', 'query', 'user', 'status', 'result_count', 'timestamp')
    list_filter = ('status', 'timestamp')
    search_fields = ('query',)

@admin.register(ProductResult)
class ProductResultAdmin(admin.ModelAdmin):
    list_display = ('id', 'title', 'platform', 'price', 'is_real_data', 'fetched_at')
    list_filter = ('platform', 'is_real_data', 'fetched_at')
    search_fields = ('title', 'category')
