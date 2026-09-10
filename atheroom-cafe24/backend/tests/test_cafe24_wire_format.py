"""Regressions found against Cafe24's real Admin API, without live writes."""
import json
import httpx
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.config import settings
from app.db import Base
from app.models import Cafe24Account
from app.services.cafe24_service import Cafe24Service
from app.services.upload_service import publish_product
from test_phase6 import fixture


def test_publishing_matches_cafe24_http_contract(monkeypatch):
    monkeypatch.setattr(settings,'demo_mode',False)
    monkeypatch.setattr(Cafe24Service,'token',lambda self,force=False:'test-token')
    monkeypatch.setattr('app.services.cafe24_service.time.sleep',lambda _:None)
    monkeypatch.setattr('app.services.image_service.encoded',lambda _:'jpeg-base64')
    seen=[]
    def handle(request):
        seen.append((request.method,request.url.path))
        if request.method=='GET':
            assert request.url.params['shop_no']=='1'
            data={'setting':{'calculate_price_based_on':'A'}} if request.url.path.endswith('/setting') else {'products':[]}
        else:
            assert not request.url.query, 'Cafe24 rejects query strings on POST and PUT'
            body=json.loads(request.content)
            if request.url.path.endswith('/products/images'):
                assert body=={'requests':[{'image':'jpeg-base64'}]}
                data={'images':[{'path':'https://example.com/photo.jpg'}]}
            elif request.url.path.endswith('/images'):
                assert body['request']['detail_image']=='data:image/jpeg;base64,jpeg-base64'
                data={'image':{k:'https://example.com/photo.jpg' for k in ('detail_image','list_image','tiny_image','small_image')}}
            elif request.method=='POST':
                assert body['request']['display']==body['request']['selling']=='F'
                data={'product':{'product_no':123}}
            else:data={'ok':True}
        return httpx.Response(201 if request.method=='POST' else 200,json=data)
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        p=fixture(db);db.add(Cafe24Account(user_id=p.user_id,mall_id='testmall',demo=False));db.commit()
        service=Cafe24Service(db,p.user_id,client=httpx.Client(transport=httpx.MockTransport(handle)))
        publish_product(db,p,service)
        assert p.status=='UPLOADED'
        assert ('POST','/api/v2/admin/products/images') in seen


def test_success_status_with_empty_main_image_is_not_complete(monkeypatch):
    from test_phase6 import Recording
    class EmptyImage(Recording):
        def request(self,method,path,params=None,payload=None):
            if path=='/products/123/images':return {'image':{'detail_image':None}}
            return super().request(method,path,params,payload)
    monkeypatch.setattr('app.services.image_service.encoded',lambda _:'jpeg-base64')
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        p=fixture(db);service=EmptyImage();service.fail=False
        publish_product(db,p,service)
        assert p.status=='PARTIAL_FAILED'
        assert p.upload_steps['main']['status']=='FAILED'
