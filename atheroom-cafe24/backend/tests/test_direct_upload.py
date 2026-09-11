import hashlib,io
import pytest
from fastapi.testclient import TestClient
from PIL import Image
from sqlalchemy import create_engine,select
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings
from app.db import Base,get_db
from app.main import app
from app.models import User,Product,ProductImage
from app.services.upload_ticket_service import issue


def test_direct_upload_is_content_bound_private_and_idempotent(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    Base.metadata.create_all(engine);factory=sessionmaker(engine,expire_on_commit=False)
    monkeypatch.setattr(settings,'bridge_token','x'*48)
    monkeypatch.setattr(settings,'frontend_origin','https://studio.example.test')
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path))
    monkeypatch.setattr(settings,'storage_backend','local')
    def override():
        with factory() as db:yield db
    app.dependency_overrides[get_db]=override
    try:
        with factory() as db:
            db.add(User(id='owner',email='owner@test'));db.flush();db.add(Product(id='product',user_id='owner'));db.commit()
        buf=io.BytesIO();Image.new('RGB',(30,30),'orange').save(buf,'PNG');raw=buf.getvalue()
        token=issue('owner','product',hashlib.sha256(raw).hexdigest())
        client=TestClient(app);client.headers['origin']='https://studio.example.test'
        # No app cookie and no bridge credential are sent to the direct URL.
        assert client.post('/api/direct-upload/'+token+'tampered',content=raw).status_code==403
        assert client.post('/api/direct-upload/'+token,content=raw+b'changed').status_code==400
        assert client.post('/api/direct-upload/'+token,content=raw,headers={'origin':'https://attacker.example'}).status_code==403
        assert client.post('/api/direct-upload/'+token,content=raw).status_code==200
        assert client.post('/api/direct-upload/'+token,content=raw).status_code==200
        with factory() as db:
            images=list(db.scalars(select(ProductImage)));assert len(images)==1
            image_id=images[0].id
        assert client.get('/api/media/'+image_id).status_code==403
        assert client.get('/api/media/'+image_id,headers={'x-studio-bridge':'x'*48}).status_code==401
        # Possession of an upload ticket grants no access to product editing.
        assert client.put('/api/products/product',json={}).status_code==403
        monkeypatch.setattr('app.services.upload_ticket_service.time.time',lambda:10**12)
        assert client.post('/api/direct-upload/'+token,content=raw).status_code==403
    finally:
        app.dependency_overrides.clear();engine.dispose()
