from django.http import JsonResponse, HttpResponse
from django.shortcuts import render, redirect
from django.db import connection
from django.views import View

def health_check(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
    except Exception:
        return JsonResponse({"status": "degraded", "db": "unreachable"}, status=503)
    return JsonResponse({"status": "ok"})

def custom_error_404(request, exception=None):
    try:
        return render(request, 'core/404.html', status=404)
    except Exception:
        return HttpResponse("Custom 404: Page Not Found", status=404)

def custom_error_500(request):
    try:
        return render(request, 'core/500.html', status=500)
    except Exception:
        return HttpResponse("Custom 500: Server Error", status=500)

def trigger_500(request):
    raise Exception("Forced 500 Error")

class HomeView(View):
    def _context(self):
        return {
            'steps': [
                'Enter product name or URL',
                'We search real-time on top platforms',
                'Compare price, rating, and AI deal recommendation'
            ],
            'platforms': ['Amazon', 'Flipkart', 'Meesho', 'Croma', 'Reliance Digital'],
            'popular_searches': ['mechanical keyboard', 'iphone 15 pro', 'running shoes', 'noise cancelling headphones']
        }

    def get(self, request):
        context = self._context()
        try:
            return render(request, 'core/home.html', context)
        except Exception:
            return HttpResponse(f"Welcome to ShopGPT! Steps: {context['steps']}, Platforms: {context['platforms']}")

    def post(self, request):
        query = request.POST.get('query', '').strip()
        from django.urls import reverse
        return redirect(reverse('products:search') + f"?q={query}")

def set_theme(request):
    theme = request.POST.get('theme', 'dark')
    if theme not in ['light', 'dark']:
        theme = 'dark'
    next_url = request.POST.get('next', '/')
    response = redirect(next_url)
    response.set_cookie('theme', theme, max_age=365*24*60*60)
    return response


