"""Fresh login tokens and a safe recovery page for expired forms."""
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.shortcuts import render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET


@never_cache
@require_GET
def csrf_token(request):
    return JsonResponse({'csrfToken': get_token(request)})


@never_cache
def csrf_failure(request, reason=''):
    # Keep the reason in Django's CSRF log, not in a public error page.
    return render(request, 'registration/csrf_failure.html', status=403)
