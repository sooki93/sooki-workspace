from datetime import datetime,timedelta,timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from fastapi.testclient import TestClient
from app.db import Base,get_db
from app.models import OAuthState
from app.main import app
from app.config import settings

def test_state_is_bound_expiring_and_one_time(monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    factory=sessionmaker(engine,expire_on_commit=False);Base.metadata.create_all(engine)
    monkeypatch.setattr('app.main.SessionLocal',factory)
    monkeypatch.setattr(settings,'frontend_origin','http://testserver')
    monkeypatch.setattr(settings,'cafe24_mall_id','testmall')
    monkeypatch.setattr(settings,'cafe24_client_id','test-client')
    monkeypatch.setattr(settings,'cafe24_client_secret','test-secret')
    def override():
        with factory() as db: yield db
    app.dependency_overrides[get_db]=override
    try:
        with TestClient(app) as client:
            client.headers['origin']='http://testserver';client.post('/api/session',json={})
            monkeypatch.setattr(settings,'demo_mode',False)
            response=client.get('/api/cafe24/connect',follow_redirects=False)
            assert response.status_code==307
            from urllib.parse import parse_qs,urlparse
            state=parse_qs(urlparse(response.headers['location']).query)['state'][0]
            assert client.get('/api/cafe24/callback?state=wrong&error=denied').status_code==400
            # A legitimate cancellation consumes the state; repeat use is rejected.
            assert client.get('/api/cafe24/callback',params={'state':state,'error':'access_denied'},follow_redirects=False).status_code==307
            assert client.get('/api/cafe24/callback',params={'state':state,'error':'access_denied'}).status_code==400
    finally: app.dependency_overrides.clear()
