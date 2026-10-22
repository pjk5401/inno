class ResponsePolicyMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response
    def __call__(self, request):
        response = self.get_response(request)
        if '/static/' not in request.path:
            response['Cache-Control'] = 'no-store, private'
        response['Permissions-Policy'] = 'geolocation=(self), camera=(), microphone=()'
        return response
