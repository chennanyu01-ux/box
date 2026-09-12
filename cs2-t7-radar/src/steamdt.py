import json
import os
import time
from urllib.request import Request, urlopen
from urllib.parse import urlencode, urlparse
from urllib.error import HTTPError, URLError


class SteamDTError(RuntimeError):
    pass


class SteamDTClient:
    def __init__(self, api_key=None, base=None, timeout=20):
        self.api_key = api_key or os.getenv('STEAMDT_API_KEY', '')
        self.base = (base or os.getenv('STEAMDT_API_BASE', 'https://open.steamdt.com')).rstrip('/')
        self.timeout = timeout
        self._last_call = {}
        if not self.api_key or self.api_key == 'replace_me':
            raise SteamDTError('STEAMDT_API_KEY is required')
        if urlparse(self.base).scheme != 'https':
            raise SteamDTError('SteamDT requires HTTPS')

    def _request(self, method, path, params=None, body=None, retries=2):
        intervals = {'/open/cs2/v1/base': 86400, '/open/cs2/v1/price/batch': 61,
                     '/open/cs2/v1/price/single': 1.1, '/open/cs2/item/v1/kline': .51}
        interval = intervals.get(path, 1)
        remaining = interval - (time.monotonic() - self._last_call.get(path, -1e12))
        if remaining > 0:
            raise SteamDTError(f'local rate limit: retry {path} after {remaining:.1f}s')
        url = self.base + path + ('?' + urlencode(params) if params else '')
        data = None if body is None else json.dumps(body).encode('utf-8')
        req = Request(url, data=data, method=method, headers={
            'Authorization': f'Bearer {self.api_key}', 'Content-Type': 'application/json',
            'Accept': 'application/json', 'User-Agent': 'cs2-t7-radar/0.2'
        })
        for attempt in range(retries + 1):
            self._last_call[path] = time.monotonic()
            try:
                with urlopen(req, timeout=self.timeout) as response:
                    payload = json.loads(response.read().decode('utf-8'))
                if not isinstance(payload, dict) or payload.get('success') is not True:
                    # No provider body, URL headers or credential echo in errors.
                    code = payload.get('errorCode', 'invalid envelope') if isinstance(payload, dict) else 'invalid envelope'
                    raise SteamDTError(f'SteamDT rejected request: {code}')
                return payload.get('data')
            except HTTPError as error:
                if error.code < 500 or attempt == retries or interval > 2:
                    raise SteamDTError(f'SteamDT HTTP {error.code}; Retry-After={error.headers.get("Retry-After", "unknown")}') from None
            except (URLError, TimeoutError, json.JSONDecodeError):
                if attempt == retries or interval > 2:
                    raise SteamDTError('SteamDT network or response error') from None
            time.sleep(max(interval, 1.5 * (attempt + 1)))

    def base_info(self):
        return self._request('GET', '/open/cs2/v1/base')

    def price_batch(self, market_hash_names):
        names = list(dict.fromkeys(market_hash_names))
        if not names or len(names) > 100:
            raise ValueError('price_batch requires 1..100 distinct marketHashNames')
        return self._request('POST', '/open/cs2/v1/price/batch', body={'marketHashNames': names})

    def price_single(self, market_hash_name):
        return self._request('GET', '/open/cs2/v1/price/single', params={'marketHashName': market_hash_name})

    def avg_price(self, market_hash_name):
        return self._request('GET', '/open/cs2/v1/price/avg', params={'marketHashName': market_hash_name})

    def item_kline(self, market_hash_name, kline_type=1, platform=None, special_style=None):
        body = {'marketHashName': market_hash_name, 'type': kline_type}
        if platform:
            body['platform'] = platform
        if special_style:
            body['specialStyle'] = special_style
        return self._request('POST', '/open/cs2/item/v1/kline', body=body)

    def broad_index(self):
        return self._request('GET', '/open/cs2/broad/v1/index')

    def broad_kline(self, kline_type=1, max_time=0):
        return self._request('POST', '/open/cs2/broad/v1/kline',
                             body={'type': kline_type, 'maxTime': max_time})
