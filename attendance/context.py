from django.conf import settings
from .views import clock_data

def common(request):
    return {'is_sandbox': settings.SANDBOX, 'prefix': settings.URL_PREFIX,
            'app_label': settings.APP_LABEL, **clock_data()}
