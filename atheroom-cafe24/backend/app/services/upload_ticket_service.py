"""Short-lived, content-bound tickets for uploads directly to the personal Mac."""
import base64
import hashlib
import hmac
import json
import time
from pathlib import Path
from urllib.parse import urlsplit
from app.config import settings
from app.models import uid


def issue(user_id, product_id, sha256):
    data={'u':user_id,'p':product_id,'i':uid(),'sha':sha256,'exp':int(time.time())+600}
    payload=base64.urlsafe_b64encode(json.dumps(data,separators=(',',':')).encode()).decode().rstrip('=')
    signature=hmac.new(settings.bridge_token.encode(),payload.encode(),hashlib.sha256).hexdigest()
    return payload+'.'+signature


def verify(token):
    try:
        if not settings.bridge_token or len(token)>2000: raise ValueError()
        payload,signature=token.split('.')
        expected=hmac.new(settings.bridge_token.encode(),payload.encode(),hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature,expected): raise ValueError()
        data=json.loads(base64.urlsafe_b64decode(payload+'='*(-len(payload)%4)))
        if data['exp']<time.time() or not all(data.get(k) for k in ('u','p','i','sha')): raise ValueError()
        return data
    except (ValueError,KeyError,TypeError):
        raise ValueError('사진 전송 승인이 만료되었습니다. 사진을 다시 선택해주세요.') from None


def public_url():
    if settings.app_env!='mac' or not settings.bridge_public_url_file: return None
    try:
        url=Path(settings.bridge_public_url_file).read_text().strip()
        parsed=urlsplit(url)
        if parsed.scheme!='https' or not parsed.hostname or parsed.username or parsed.password or parsed.path or parsed.query:
            return None
        return url
    except OSError: return None
