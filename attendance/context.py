from django.conf import settings

def common(request):
    return {'is_sandbox': settings.SANDBOX, 'prefix': settings.URL_PREFIX,
            'app_label': settings.APP_LABEL}
