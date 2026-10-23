import base64
import binascii
import json
from urllib.parse import urlsplit

from cryptography.hazmat.primitives.asymmetric import ec
from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.middleware.csrf import get_token
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from .models import PushSubscription
from .push import configured


def validate_endpoint(endpoint):
    if not isinstance(endpoint,str) or len(endpoint)>2048:
        raise ValueError
    url = urlsplit(endpoint)
    host = (url.hostname or '').lower()
    trusted = host in ('fcm.googleapis.com','updates.push.services.mozilla.com','push.services.mozilla.com') or host.endswith('.push.apple.com')
    if not trusted or url.scheme!='https' or url.username or url.password or url.port not in (None,443) or url.fragment:
        raise ValueError
    return endpoint


def decode_key(value, size):
    if not isinstance(value,str) or len(value)>120:
        raise ValueError
    decoded = base64.b64decode(value+'='*(-len(value)%4),altchars=b'-_',validate=True)
    if len(decoded)!=size:
        raise ValueError
    return decoded


def body(request):
    if request.content_type!='application/json' or len(request.body)>8192:
        raise ValueError
    data = json.loads(request.body)
    if not isinstance(data,dict):
        raise ValueError
    return data


@login_required
@never_cache
@require_GET
def push_config(request):
    return JsonResponse({'available':configured(),'publicKey':settings.PUSH_VAPID_PUBLIC_KEY if configured() else '',
                         'csrfToken':get_token(request),'userId':request.user.pk})


@login_required
@never_cache
@require_POST
def subscribe(request):
    if not configured():
        return JsonResponse({'error':'Notifications are not configured on the server yet.'},status=503)
    try:
        data = body(request)
        endpoint = validate_endpoint(data.get('endpoint'))
        keys = data.get('keys')
        if not isinstance(keys,dict):
            raise ValueError
        public = decode_key(keys.get('p256dh'),65)
        decode_key(keys.get('auth'),16)
        ec.EllipticCurvePublicKey.from_encoded_point(ec.SECP256R1(),public)
    except (ValueError,TypeError,binascii.Error,UnicodeDecodeError):
        return JsonResponse({'error':'Invalid push subscription.'},status=400)
    if not request.user.push_subscriptions.filter(endpoint=endpoint).exists() and request.user.push_subscriptions.count()>=20:
        return JsonResponse({'error':'This account already has 20 notification devices. Disable notifications on an unused device first.'},status=400)
    # A shared phone's subscription belongs to its current signed-in account.
    sub,_ = PushSubscription.objects.update_or_create(endpoint=endpoint,defaults={
        'user':request.user,'p256dh':keys['p256dh'],'auth':keys['auth']})
    request.session['push_subscription_id'] = sub.pk
    return JsonResponse({'ok':True})


@login_required
@never_cache
@require_POST
def unsubscribe(request):
    try:
        endpoint = validate_endpoint(body(request).get('endpoint'))
    except (ValueError,TypeError,UnicodeDecodeError):
        return JsonResponse({'error':'Invalid subscription.'},status=400)
    PushSubscription.objects.filter(user=request.user,endpoint=endpoint).delete()
    request.session.pop('push_subscription_id',None)
    return JsonResponse({'ok':True})
