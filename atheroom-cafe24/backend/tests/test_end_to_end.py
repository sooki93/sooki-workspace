import io
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine,select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.db import Base,get_db
from app.models import Job,Product,User,TemplateProfile
from app.main import app
from app.worker import execute
from app.config import settings

def test_complete_operator_flow(tmp_path,monkeypatch):
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    factory=sessionmaker(engine,expire_on_commit=False);Base.metadata.create_all(engine)
    monkeypatch.setattr('app.main.SessionLocal',factory)
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path))
    monkeypatch.setattr(settings,'frontend_origin','http://testserver')
    def override():
        with factory() as db: yield db
    app.dependency_overrides[get_db]=override
    def drain():
        with factory() as db:
            for job in db.scalars(select(Job).where(Job.status=='QUEUED')): execute(db,job)
    try:
        with TestClient(app) as c:
            c.headers['origin']='http://testserver'
            assert c.get('/api/products').status_code==401
            assert c.post('/api/session',json={}).status_code==200
            assert c.post('/api/demo/connect').status_code==200
            drain()
            profiles=c.get('/api/templates').json();assert profiles[0]['status']=='DRAFT'
            assert c.post('/api/templates/'+profiles[0]['id']+'/activate').status_code==200
            p=c.post('/api/products').json();id=p['id']
            pic=io.BytesIO();Image.new('RGB',(100,100),'orange').save(pic,'PNG')
            assert c.post(f'/api/products/{id}/images',files=[('files',('test.png',pic.getvalue(),'image/png'))]).status_code==200
            assert c.post(f'/api/products/{id}/generate').status_code==200;drain()
            p=c.get('/api/products/'+id).json();assert p['status']=='NEEDS_INPUT'
            assert p['price'] is None and p['material']==''
            payload={k:p[k] for k in ['revision','product_name','price','supply_price','internal_product_group','cafe24_category_id','description','material','size','keywords','main_image_id','reference_product_id']}
            payload.update({'product_name':'검증용 반지','price':28000,'supply_price':12000,'material':'사용자 확인 소재','size':'사용자 확인 사이즈','internal_product_group':'RING','cafe24_category_id':42,'seo_title':'반지','seo_description':'제품 설명'})
            r=c.put('/api/products/'+id,json=payload);assert r.status_code==200,r.text;p=r.json()
            r=c.put(f'/api/products/{id}/images',json={'revision':p['revision'],'main_image_id':p['main_image_id'],'images':[{'id':i['id'],'image_type':'PRODUCT','confirmed':True} for i in p['images']]});assert r.status_code==200,r.text
            p=c.get('/api/products/'+id).json()
            assert not p['missing_fields']
            assert '기존 상품 소재' not in p['rendered_html'] and '사용자 확인 소재' in p['rendered_html']
            assert c.post(f'/api/products/{id}/publish',json={'revision':p['revision']}).status_code==409
            r=c.post(f'/api/products/{id}/review',json={'revision':p['revision'],'acknowledge_warnings':True});assert r.status_code==200,r.text
            assert c.post(f'/api/products/{id}/publish',json={'revision':p['revision']}).status_code==200
            assert c.post(f'/api/products/{id}/publish',json={'revision':p['revision']}).status_code==409
            drain();p=c.get('/api/products/'+id).json();assert p['status']=='UPLOADED',p
            assert all(v['status']=='DONE' for v in p['upload_steps'].values())
            assert c.post('/api/templates/analyze').status_code==200;drain()
            profiles=c.get('/api/templates').json();assert profiles[0]['status']=='DRAFT' and profiles[1]['status']=='ACTIVE'
            assert c.post('/api/templates/'+profiles[0]['id']+'/activate').status_code==200
            assert c.get('/api/templates').json()[1]['status']=='ARCHIVED'
            # Tenant isolation, even if a product/image UUID is known.
            with factory() as db:
                stranger=User(email='stranger@example.com');db.add(stranger);db.flush();foreign=Product(user_id=stranger.id);db.add(foreign);db.commit();foreign_id=foreign.id
            assert c.get('/api/products/'+foreign_id).status_code==404
            c.headers['origin']='https://evil.example';assert c.post('/api/products').status_code==403
    finally: app.dependency_overrides.clear()
