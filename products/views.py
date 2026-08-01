from django.shortcuts import render, redirect, get_object_or_404
from django.views import View
from django.views.generic import DetailView, ListView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.contrib import messages
from products.models import SearchQuery, ProductResult
from products.services import dispatch_search
import logging

logger = logging.getLogger('products')


def error_message_for(search):
    if search.status == 'failed':
        if search.failure_reason == 'api_unavailable':
            return "The search API is currently unavailable. Please try again later."
        elif search.failure_reason == 'not_configured':
            return "Search provider is not configured. Please setup your API keys."
        else:
            return "An unexpected error occurred during search. Please try again."
    elif search.status == 'completed' and search.result_count == 0:
        return "No matching products found."
    return None

class SearchView(View):
    def post(self, request):
        query = request.POST.get('query', '').strip()
        location = request.POST.get('location', '').strip() or 'India'
        if not query:
            messages.error(request, "Search query cannot be empty.")
            return redirect('home')

        user = request.user if request.user.is_authenticated else None
        session_key = request.session.session_key
        if not session_key:
            request.session.create()
            session_key = request.session.session_key

        search = SearchQuery.objects.create(
            user=user,
            query=query,
            location=location,
            session_key=session_key
        )

        dispatch_search(query, search.id)
        return redirect('products:results', search_id=search.id)

    def get(self, request):
        return redirect('home')

class ResultsView(DetailView):
    model = SearchQuery
    template_name = 'products/results.html'
    pk_url_kwarg = 'search_id'
    context_object_name = 'search'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        search = self.object
        
        from django.core.paginator import Paginator, EmptyPage, PageNotAnInteger
        from django.conf import settings
        page_size = getattr(settings, 'PRODUCTS_PAGE_SIZE', 20)
        
        queryset = ProductResult.objects.for_search(search)
        paginator = Paginator(queryset, page_size)
        page_num = self.request.GET.get('page', 1)
        try:
            results_page = paginator.page(page_num)
        except PageNotAnInteger:
            results_page = paginator.page(1)
        except EmptyPage:
            results_page = paginator.page(paginator.num_pages)
            
        context['results'] = results_page
        context['error_message'] = error_message_for(search)
        context['is_paginated'] = paginator.num_pages > 1
        return context

class ComparisonView(View):
    def get(self, request, search_id):
        search = get_object_or_404(SearchQuery, pk=search_id)
        sort = request.GET.get('sort', 'price')
        direction = request.GET.get('dir', 'asc')
        platform_filter = request.GET.get('platform', '').strip().lower()

        queryset = ProductResult.objects.for_search(search)
        available_platforms = list(queryset.values_list('platform', flat=True).distinct())

        if platform_filter:
            queryset = queryset.filter(platform=platform_filter)

        from django.db.models import F

        if sort == 'price':
            if direction == 'desc':
                queryset = queryset.order_by(F('price').desc(nulls_last=True))
            else:
                queryset = queryset.order_by(F('price').asc(nulls_last=True))
        elif sort == 'rating':
            if direction == 'desc':
                queryset = queryset.order_by(F('rating').desc(nulls_last=True))
            else:
                queryset = queryset.order_by(F('rating').asc(nulls_last=True))

        context = {
            'search': search,
            'results': queryset,
            'available_platforms': available_platforms,
            'selected_platform': platform_filter,
            'error_message': error_message_for(search)
        }
        return render(request, 'products/compare.html', context)

class TopRecommendationsView(View):
    def get(self, request, search_id):
        search = get_object_or_404(SearchQuery, pk=search_id)
        
        results = list(ProductResult.objects.filter(search=search, price__isnull=False))
        eligible = []
        for r in results:
            in_stock = r.raw_data.get('in_stock', True) if isinstance(r.raw_data, dict) else True
            if in_stock is not False:
                eligible.append(r)
                
        from ml.services import predict_fair_price, predict_deal_quality, DEAL_BADGE_MAP
        from integrations.base import ProductDTO
        
        ml_results = []
        has_ml = False
        
        for r in eligible:
            try:
                dto = ProductDTO(
                    title=r.title,
                    price=r.price,
                    price_str=r.price_str,
                    product_url=r.product_url,
                    platform=r.platform,
                    image_url=r.image_url,
                    rating=r.rating,
                    raw_payload=r.raw_data
                )
            except Exception as e:
                logger.warning(f"Skipping product ID {r.id} for recommendations due to DTO conversion error: {e}")
                continue

            fair_price = predict_fair_price(dto)
            if fair_price is not None:
                has_ml = True
                discount = float(fair_price - r.price) / float(fair_price) if fair_price > 0 else 0.0
                ml_results.append((r, fair_price, discount))
            else:
                ml_results.append((r, None, 0.0))
                
        recs_with_reasons = []
        if has_ml:
            ml_results.sort(key=lambda x: x[2], reverse=True)
            recommendations = ml_results[:3]
            
            reasons = [
                "Top ML recommendation: Best deal score (greatest discount relative to estimated fair price)",
                "Second best deal score according to our fair price model",
                "Third best deal score according to our fair price model"
            ]
            for i, (rec, fair_price, discount) in enumerate(recommendations):
                deal_label = predict_deal_quality(
                    ProductDTO(
                        title=rec.title,
                        price=rec.price,
                        price_str=rec.price_str,
                        product_url=rec.product_url,
                        platform=rec.platform,
                        image_url=rec.image_url,
                        rating=rec.rating,
                        raw_payload=rec.raw_data
                    )
                )
                
                diff_pct = int(round(discount * 100))
                if diff_pct > 0:
                    reason_desc = f"{diff_pct}% below the typical fair price for this product."
                elif diff_pct < 0:
                    reason_desc = f"{abs(diff_pct)}% above the typical fair price for this product."
                else:
                    reason_desc = "Priced exactly at the estimated typical fair price."
                    
                recs_with_reasons.append({
                    'product': rec,
                    'reason': f"{reason_desc} (Estimated Fair Price: {fair_price})",
                    'fair_price': fair_price,
                    'deal_quality': deal_label,
                    'deal_badge': DEAL_BADGE_MAP.get(deal_label, '') if deal_label else '',
                })
            ml_backed = True
        else:
            eligible.sort(key=lambda x: x.price)
            recommendations = eligible[:3]
            reasons = [
                "Lowest price among in-stock listings for this search (ranked by price)",
                "Second lowest price among in-stock listings (ranked by price)",
                "Third lowest price among in-stock listings (ranked by price)"
            ]
            for i, rec in enumerate(recommendations):
                recs_with_reasons.append({
                    'product': rec,
                    'reason': reasons[i],
                    'deal_quality': None,
                    'deal_badge': '',
                })
            ml_backed = False

        context = {
            'search': search,
            'recommendations': recs_with_reasons,
            'ml_backed': ml_backed,
            'error_message': error_message_for(search)
        }
        return render(request, 'products/recommendations.html', context)

class HistoryView(LoginRequiredMixin, ListView):
    model = SearchQuery
    template_name = 'products/history.html'
    login_url = 'accounts:login'

    def get_queryset(self):
        return SearchQuery.objects.recent_for_user(self.request.user)
