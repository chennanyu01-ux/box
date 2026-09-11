import json, os, time
from urllib.request import Request, urlopen
from urllib.parse import urlencode
from urllib.error import HTTPError, URLError

class SteamDTError(RuntimeError):
    pass

class SteamDTClient:
    def __init__(self, api_key=None, base=None, timeout=20):
        self.api_key = api_key or os.getenv('STEAMDT_API_KEY', '')
        self.base = (base or os.getenv('STEAMDT_API_BASE', 'https://open.steamdt.com')).rstrip('/')
        self.timeout = timeout
        if not self.api_key:
            raise SteamDTError('STEAMDT_API_KEY is required')

    def _request(self, method, path, params=None, body=None, retries=2):
        url = self.base + path
        if params:
            url += '?' + urlencode(params)
        data = None if body is None else json.dumps(body).encode('utf-8')
        req = Request(url, data=data, method=method, headers={
            'Authorization': f'Bearer {self.api_key}',
            'Content-Type': 'application/json',
            'Accept': 'application/json',
            'User-Agent': 'cs2-t7-radar/0.1'
        })
        last = None
        for attempt in range(retries + 1):
            try:
                with urlopen(req, timeout=self.timeout) as r:
                    payload = json.loads(r.read().decode('utf-8'))
                if not payload.get('success', False):
                    raise SteamDTError(f"SteamDT API error {payload.get('errorCode')}: {payload.get('errorMsg')}")
                return payload.get('data')
            except (HTTPError, URLError, TimeoutError, json.JSONDecodeError, SteamDTError) as e:
                last = e
                if attempt < retries:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                raise SteamDTError(str(last)) from last

    def base_info(self):
        return self._request('GET', '/open/cs2/v1/base')

    def price_batch(self, market_hash_names):
        names = list(market_hash_names)
        if not names or len(names) > 100:
            raise ValueError('price_batch requires 1..100 marketHashNames')
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
