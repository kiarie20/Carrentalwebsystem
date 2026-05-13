import base64
import json
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from urllib import error, parse, request

from django.conf import settings


class MpesaConfigurationError(Exception):
    pass


class MpesaGatewayError(Exception):
    pass


def mpesa_is_configured():
    return all(
        [
            settings.MPESA_CONSUMER_KEY,
            settings.MPESA_CONSUMER_SECRET,
            settings.MPESA_SHORTCODE,
            settings.MPESA_PASSKEY,
            settings.MPESA_CALLBACK_URL,
        ]
    )


def normalize_phone_number(phone_number):
    digits = ''.join(ch for ch in (phone_number or '') if ch.isdigit())
    if digits.startswith('0'):
        digits = f"254{digits[1:]}"
    elif digits.startswith('7'):
        digits = f"254{digits}"
    elif digits.startswith('254'):
        digits = digits
    else:
        raise MpesaGatewayError('Use a valid Kenyan phone number for M-Pesa.')

    if len(digits) != 12 or not digits.startswith('254'):
        raise MpesaGatewayError('Use a valid Kenyan phone number for M-Pesa.')

    return digits


def _base_url():
    if settings.MPESA_ENVIRONMENT == 'live':
        return 'https://api.safaricom.co.ke'
    return 'https://sandbox.safaricom.co.ke'


def _json_request(url, payload=None, headers=None, method='GET'):
    data = None
    request_headers = headers or {}
    if payload is not None:
        data = json.dumps(payload).encode('utf-8')
        request_headers = {'Content-Type': 'application/json', **request_headers}

    http_request = request.Request(url, data=data, headers=request_headers, method=method)
    try:
        with request.urlopen(http_request, timeout=30) as response:
            raw_body = response.read().decode('utf-8')
            return json.loads(raw_body) if raw_body else {}
    except error.HTTPError as exc:
        raw_body = exc.read().decode('utf-8', errors='ignore')
        raise MpesaGatewayError(raw_body or f'M-Pesa request failed with status {exc.code}.') from exc
    except error.URLError as exc:
        raise MpesaGatewayError('Unable to reach the M-Pesa gateway from this environment.') from exc


def get_access_token():
    if not mpesa_is_configured():
        raise MpesaConfigurationError('M-Pesa credentials are missing from settings.')

    credentials = f"{settings.MPESA_CONSUMER_KEY}:{settings.MPESA_CONSUMER_SECRET}".encode('utf-8')
    encoded_credentials = base64.b64encode(credentials).decode('utf-8')
    url = f"{_base_url()}/oauth/v1/generate?grant_type=client_credentials"
    response = _json_request(url, headers={'Authorization': f'Basic {encoded_credentials}'})
    token = response.get('access_token')
    if not token:
        raise MpesaGatewayError('No M-Pesa access token was returned.')
    return token


def initiate_stk_push(*, amount, phone_number, account_reference, transaction_desc):
    token = get_access_token()
    normalized_phone = normalize_phone_number(phone_number)
    timestamp = datetime.now().strftime('%Y%m%d%H%M%S')
    password = base64.b64encode(
        f"{settings.MPESA_SHORTCODE}{settings.MPESA_PASSKEY}{timestamp}".encode('utf-8')
    ).decode('utf-8')
    rounded_amount = int(Decimal(amount).quantize(Decimal('1'), rounding=ROUND_HALF_UP))

    payload = {
        'BusinessShortCode': settings.MPESA_SHORTCODE,
        'Password': password,
        'Timestamp': timestamp,
        'TransactionType': settings.MPESA_TRANSACTION_TYPE,
        'Amount': rounded_amount,
        'PartyA': normalized_phone,
        'PartyB': settings.MPESA_SHORTCODE,
        'PhoneNumber': normalized_phone,
        'CallBackURL': settings.MPESA_CALLBACK_URL,
        'AccountReference': account_reference[:12],
        'TransactionDesc': transaction_desc[:13],
    }
    url = f"{_base_url()}/mpesa/stkpush/v1/processrequest"
    response = _json_request(url, payload=payload, headers={'Authorization': f'Bearer {token}'}, method='POST')
    response['normalized_phone'] = normalized_phone
    return response
