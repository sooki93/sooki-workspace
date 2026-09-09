from app.services.cafe24_service import Cafe24Service
from app.security import password_hash, verify_password, encrypt, decrypt
from app.config import settings
from cryptography.fernet import Fernet

def test_recent_uses_creation_not_update():
    service=object.__new__(Cafe24Service)
    calls=[]
    service.request=lambda *a,**kw: (calls.append(kw) or {'products':[]})
    assert service.recent()==[]
    assert calls[0]['params']=={'sort':'created_date','order':'desc','limit':30,'offset':0}
def test_credentials_are_encrypted(monkeypatch):
    monkeypatch.setattr(settings,'token_encryption_key',Fernet.generate_key().decode())
    encrypted=encrypt('sensitive-token')
    assert encrypted!='sensitive-token' and decrypt(encrypted)=='sensitive-token'
    value=password_hash('secure-local-password')
    assert verify_password('secure-local-password',value)
    assert not verify_password('wrong',value)
