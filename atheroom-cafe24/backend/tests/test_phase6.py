from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from app.db import Base
from app.models import User,Product,ProductImage
from app.services.upload_service import publish_product,DemoCommerce
from app.services.cafe24_service import RemoteFailure
from app.services.template_analysis_service import demo_sources
from app.services.html_parser_service import parse_html,compile_template
import pytest
class Recording(DemoCommerce):
    def __init__(self): self.calls=[]; self.fail=True
    def create_product(self,payload):
        self.calls.append(('create',payload));return {'product_no':123}
    def request(self,method,path,params=None,payload=None):
        self.calls.append((path,payload))
        if path=='/products/images' and self.fail: self.fail=False; raise RemoteFailure()
        return super().request(method,path,params,payload)
def fixture(db):
    u=User(email='x@y');db.add(u);db.flush()
    t=compile_template([{'product_no':i,'parsed':parse_html(demo_sources()[0]['description'])} for i in range(3)])
    p=Product(user_id=u.id,product_name='신규 상품',price=15000,supply_price=7000,template_snapshot=t,status='UPLOADING',cafe24_category_id=42)
    db.add(p);db.flush()
    image=ProductImage(product_id=p.id,file_url='/image',storage_key='test',file_hash='a',perceptual_hash='0'*16,sort_order=0)
    db.add(image);db.flush();p.main_image_id=image.id;db.commit();return p

def test_partial_failure_retries_only_unfinished(monkeypatch):
    monkeypatch.setattr('app.services.image_service.encoded',lambda key:'encoded-data')
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        p=fixture(db);service=Recording();publish_product(db,p,service)
        assert p.status=='PARTIAL_FAILED' and p.cafe24_product_no==123
        publish_product(db,p,service)
        assert p.status=='UPLOADED'
        assert len([c for c in service.calls if c[0]=='create'])==1
        assert len([c for c in service.calls if c[0]=='/products/123/seo'])==1
        payload=next(c[1] for c in service.calls if c[0]=='create')
        assert payload['display']=='F' and payload['selling']=='F' and payload['supply_price']=='7000'
def test_unknown_create_is_never_reissued():
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        p=fixture(db);p.upload_steps={'create':{'status':'UNKNOWN'}};db.commit()
        service=Recording();publish_product(db,p,service)
        assert p.status=='FAILED' and not p.cafe24_product_no and not service.calls

def test_product_price_basis_is_checked_before_creating():
    class ProductPriceShop(Recording):
        def request(self,method,path,params=None,payload=None):
            if path=='/products/setting': return {'setting':{'calculate_price_based_on':'B'}}
            return super().request(method,path,params,payload)
    engine=create_engine('sqlite://');Base.metadata.create_all(engine)
    with Session(engine,expire_on_commit=False) as db:
        p=fixture(db);service=ProductPriceShop()
        with pytest.raises(RemoteFailure):publish_product(db,p,service)
        assert p.cafe24_product_no is None
        assert not any(c[0]=='create' for c in service.calls)
