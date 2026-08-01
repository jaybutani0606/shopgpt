from django.conf import settings
from django.urls import reverse

class GuestSearchLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # We check if the request is a POST to the search endpoint and user is anonymous
        # The search endpoint path is typically '/products/search/'
        # We can dynamically resolve it or use the string path.
        search_path = None
        try:
            search_path = reverse('products:search')
        except Exception:
            search_path = '/products/search/'

        if request.path == search_path and request.method == 'POST':
            if not request.user.is_authenticated:
                count = request.session.get('guest_search_count', 0)
                count += 1
                request.session['guest_search_count'] = count
                
                limit = getattr(settings, 'GUEST_SEARCH_LIMIT', 2)
                if count >= limit:
                    request.session['show_auth_modal'] = True
                else:
                    request.session['show_auth_modal'] = False

        response = self.get_response(request)
        return response
