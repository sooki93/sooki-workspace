import re, time
from datetime import datetime, timedelta, timezone
from urllib.parse import urlencode
import httpx
from fastapi import HTTPException
from sqlalchemy import select
from app.config import settings
from app.models import Cafe24Account
from app.security import encrypt, decrypt, utc

class RemoteFailure(Exception):
    def __init__(self, message='쇼핑몰 연결이 원활하지 않습니다. 잠시 후 다시 시도해주세요.', ambiguous=False):
        super().__init__(message)
        self.ambiguous = ambiguous

class Cafe24Service:
    def __init__(self, db, user_id, client=None):
        self.db, self.user_id = db, user_id
        self.account = db.scalar(select(Cafe24Account).where(Cafe24Account.user_id == user_id))
        if not self.account: raise RemoteFailure('먼저 카페24 쇼핑몰을 연결해주세요.')
        self.mall = self.account.mall_id
        if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,49}', self.mall): raise RemoteFailure('쇼핑몰 연결 정보를 확인해주세요.')
        self.client = client or httpx.Client(timeout=40, follow_redirects=False)
    def close(self): self.client.close()
    def token(self, force=False):
        account = self.db.scalar(select(Cafe24Account).where(Cafe24Account.id == self.account.id).with_for_update().execution_options(populate_existing=True))
        if force or utc(account.expires_at) <= datetime.now(timezone.utc) + timedelta(minutes=2):
            data = exchange_token(self.mall, {'grant_type':'refresh_token', 'refresh_token':decrypt(account.refresh_token)}, self.client)
            store_tokens(account, data)
        token = decrypt(account.access_token)
        self.db.commit()
        return token
    def request(self, method, path, params=None, payload=None):
        if settings.demo_mode or self.account.demo: raise RemoteFailure('체험 모드에서는 실제 쇼핑몰에 전송하지 않습니다.')
        for attempt in range(4):
            token = self.token()
            time.sleep(.51)
            try:
                # Cafe24 rejects query strings on POST/PUT; their shop_no belongs in the JSON body.
                query = {'shop_no':settings.cafe24_shop_no, **(params or {})} if method in ('GET','DELETE') else None
                response = self.client.request(method, f'https://{self.mall}.cafe24api.com/api/v2/admin{path}', params=query, json=payload, headers={'Authorization':f'Bearer {token}', 'X-Cafe24-Api-Version':settings.cafe24_api_version})
            except httpx.TransportError as exc:
                if method == 'GET' and attempt < 3: time.sleep(2**attempt); continue
                raise RemoteFailure(ambiguous=method != 'GET') from exc
            if response.status_code == 401 and attempt == 0:
                self.token(force=True); continue
            if response.status_code == 429 and attempt < 3:
                waits = [response.headers.get(k, '0') for k in ['Retry-After','X-Cafe24-Call-Remain','X-Cafe24-Time-Remain']]
                time.sleep(min(60, max([2**attempt] + [float(v) for v in waits if v.replace('.','',1).isdigit()])))
                continue
            if response.status_code >= 500:
                if method == 'GET' and attempt < 3: time.sleep(2**attempt); continue
                raise RemoteFailure(ambiguous=method != 'GET')
            if response.is_error: raise RemoteFailure('쇼핑몰에서 요청을 처리하지 못했습니다. 입력 내용과 연결 권한을 확인해주세요.')
            return response.json()
        raise RemoteFailure()
    def recent(self, limit=30, offset=0):
        return self.request('GET','/products', params={'sort':'created_date','order':'desc','limit':limit,'offset':offset})['products']
    def detail(self, number): return self.request('GET', f'/products/{number}', params={'embed':'seo'})['product']
    def categories(self):
        rows=[]
        for offset in range(0, 10000, 100):
            page=self.request('GET','/categories',params={'limit':100,'offset':offset})['categories']
            rows.extend(page)
            if len(page)<100: return rows
        raise RemoteFailure('분류가 너무 많아 불러오지 못했습니다. 운영 담당자에게 문의해주세요.')
    def find_code(self, code):
        rows=self.request('GET','/products',params={'custom_product_code':code,'limit':100})['products']
        return [p for p in rows if p.get('custom_product_code') == code]
    def create_product(self, payload):
        return self.request('POST','/products',payload={'shop_no':settings.cafe24_shop_no,'request':payload})['product']
    def update_product(self, number, payload):
        return self.request('PUT',f'/products/{number}',payload={'shop_no':settings.cafe24_shop_no,'request':payload})

def auth_url(state):
    if settings.demo_mode: raise HTTPException(400,'체험 모드에서는 실제 쇼핑몰을 연결하지 않습니다.')
    mall=settings.cafe24_mall_id
    if not re.fullmatch(r'[a-z0-9][a-z0-9-]{0,49}', mall) or not settings.cafe24_client_id or not settings.cafe24_client_secret:
        raise HTTPException(503, '쇼핑몰 연결 준비가 필요합니다. 운영 담당자에게 문의해주세요.')
    return f'https://{mall}.cafe24api.com/api/v2/oauth/authorize?' + urlencode({'response_type':'code','client_id':settings.cafe24_client_id,'redirect_uri':settings.cafe24_redirect_uri,'scope':'mall.read_product,mall.write_product,mall.read_category,mall.read_store','state':state})
def exchange_token(mall, data, client):
    try:
        r=client.post(f'https://{mall}.cafe24api.com/api/v2/oauth/token', data=data, auth=(settings.cafe24_client_id, settings.cafe24_client_secret))
        r.raise_for_status()
        result=r.json()
        if result.get('mall_id') != mall: raise ValueError('mall mismatch')
        return result
    except (httpx.HTTPError, ValueError) as exc: raise RemoteFailure('쇼핑몰 연결 승인이 만료되었습니다. 다시 연결해주세요.') from exc

def store_tokens(account, data):
    account.access_token=encrypt(data['access_token'])
    account.refresh_token=encrypt(data['refresh_token'])
    value=datetime.fromisoformat(data['expires_at'].replace('Z','+00:00'))
    account.expires_at=value if value.tzinfo else value.replace(tzinfo=timezone(timedelta(hours=9)))
