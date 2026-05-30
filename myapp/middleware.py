from django.utils.cache import add_never_cache_headers

class PreventCacheMiddleware:
    """
    Middleware to prevent browser caching of pages for authenticated users.
    This ensures that when a user logs out, they cannot click the browser's
    'Back' button to view cached authenticated pages.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        
        # If the user is authenticated, prevent browser caching of the response
        if hasattr(request, 'user') and request.user.is_authenticated:
            add_never_cache_headers(response)
            response['Cache-Control'] = 'no-cache, no-store, must-revalidate, private'
            response['Pragma'] = 'no-cache'
            response['Expires'] = '0'
            
        return response
