import base64
import io
import json
from pathlib import Path
import sys
import pytest
from PIL import Image
from app.config import settings
from app.schemas.ai import ProductAnalysis
from app.services import codex_service, openai_service
from app.services.ai_errors import AIConnectionRequired, AIUsageLimit
from app.services.cafe24_service import RemoteFailure


def draft(image_id='photo-1'):
    return {'product_group':{'value':'RING','confidence':.95},'product_name':'둥근 반지',
            'description':'둥근 형태의 반지입니다.','category_recommendation':{'value':'RING','confidence':.95},
            'search_keywords':['반지'],'seo_title':'반지','seo_description':'둥근 반지',
            'images':[{'id':image_id,'type':'PRODUCT','confidence':.9}], 'missing_fields':['material','size']}


def fake_cli(tmp_path, monkeypatch, mode='success'):
    trace=tmp_path/'trace.json';cli=tmp_path/'codex-test'
    cli.write_text(f'''#!{sys.executable}
import json, os, sys
from pathlib import Path
if sys.argv[1:]==['login','status']:
    print('Logged in using {'API key' if mode=='api' else 'ChatGPT'}');sys.exit(0)
a=sys.argv;prompt=sys.stdin.read()
images=[a[i+1] for i,x in enumerate(a) if x=='--image']
Path({str(trace)!r}).write_text(json.dumps({{'args':a,'env_keys':list(os.environ),'prompt':prompt,'images_exist':all(Path(p).exists() for p in images),'cwd':os.getcwd()}}))
if {mode!r}=='limit':
    print(json.dumps({{'type':'turn.failed','error':{{'code':'usage_limit_reached'}}}}));sys.exit(1)
if {mode!r}=='timeout':
    import time;time.sleep(10)
Path(a[a.index('--output-last-message')+1]).write_text({('{"price":1234}' if mode=='bad' else json.dumps(draft()))!r})
print('{{"type":"turn.completed"}}')
''')
    cli.chmod(0o700);monkeypatch.setattr(settings,'codex_binary',str(cli))
    return trace


def test_photos_schema_and_subscription_without_api_credentials(tmp_path,monkeypatch):
    trace=fake_cli(tmp_path,monkeypatch)
    for key in ('OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','CAFE24_CLIENT_SECRET'):
        monkeypatch.setenv(key,'test-only')
    image=io.BytesIO();Image.new('RGB',(32,32),'orange').save(image,'JPEG')
    result=codex_service.parse(ProductAnalysis,[{'type':'input_text','text':'Image ID: photo-1'},
       {'type':'input_image','image_url':'data:image/jpeg;base64,'+base64.b64encode(image.getvalue()).decode()}], 'Only inspect input.')
    assert result==draft()
    run=json.loads(trace.read_text())
    assert run['images_exist'] and 'Image ID: photo-1' in run['prompt']
    assert '--output-schema' in run['args'] and '--ignore-user-config' in run['args']
    assert 'forced_login_method="chatgpt"' in run['args'] and 'features.shell_tool=false' in run['args']
    assert not {'OPENAI_API_KEY','CODEX_API_KEY','OPENAI_BASE_URL','CAFE24_CLIENT_SECRET'} & set(run['env_keys'])
    assert not Path(run['cwd']).exists()


def test_api_login_is_rejected_before_model_call(tmp_path,monkeypatch):
    trace=fake_cli(tmp_path,monkeypatch,'api')
    with pytest.raises(AIConnectionRequired): codex_service.parse(ProductAnalysis,[], '')
    assert not trace.exists()


def test_limit_never_falls_back_to_api(tmp_path,monkeypatch):
    trace=fake_cli(tmp_path,monkeypatch,'limit')
    monkeypatch.setattr(settings,'ai_provider','codex');monkeypatch.setattr(settings,'openai_api_key','test-only')
    monkeypatch.setattr(openai_service,'OpenAI',lambda **kw: pytest.fail('API fallback forbidden'))
    with pytest.raises(AIUsageLimit): openai_service.parse(ProductAnalysis,[])
    assert not Path(json.loads(trace.read_text())['cwd']).exists()


def test_invalid_ai_output_is_rejected(tmp_path,monkeypatch):
    fake_cli(tmp_path,monkeypatch,'bad')
    with pytest.raises(RemoteFailure): codex_service.parse(ProductAnalysis,[], '')


def test_timeout_stops_process_and_cleans_up(tmp_path,monkeypatch):
    trace=fake_cli(tmp_path,monkeypatch,'timeout');monkeypatch.setattr(settings,'codex_timeout_seconds',.2)
    with pytest.raises(RemoteFailure,match='응답 시간'): codex_service.parse(ProductAnalysis,[], '')
    assert not Path(json.loads(trace.read_text())['cwd']).exists()


def test_remote_image_urls_are_not_fetched(tmp_path,monkeypatch):
    trace=fake_cli(tmp_path,monkeypatch)
    with pytest.raises(RemoteFailure):
        codex_service.parse(ProductAnalysis,[{'type':'input_image','image_url':'https://example.test/photo.jpg'}], '')
    assert not trace.exists()


def test_product_copy_is_not_treated_as_limit_error():
    assert 'usage limit' not in codex_service.failure_details(json.dumps({'type':'item.completed','item':{'text':'usage limit'}}),'')


def test_waiting_draft_survives_and_restarts_without_real_shop_publish(tmp_path,monkeypatch):
    from fastapi.testclient import TestClient
    from sqlalchemy import create_engine,select
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy.pool import StaticPool
    from app.db import Base,get_db
    from app.main import app
    from app.models import Job,Product,AIGeneration
    from app.worker import execute
    engine=create_engine('sqlite://',connect_args={'check_same_thread':False},poolclass=StaticPool)
    factory=sessionmaker(engine,expire_on_commit=False);Base.metadata.create_all(engine)
    monkeypatch.setattr('app.main.SessionLocal',factory)
    monkeypatch.setattr(settings,'demo_mode',True);monkeypatch.setattr(settings,'demo_ai_enabled',True)
    monkeypatch.setattr(settings,'upload_dir',str(tmp_path));monkeypatch.setattr(settings,'frontend_origin','http://testserver')
    def override():
        with factory() as db: yield db
    def drain():
        with factory() as db:
            for job in db.scalars(select(Job).where(Job.status=='QUEUED')): execute(db,job)
    def limit(*a,**k): raise AIUsageLimit()
    app.dependency_overrides[get_db]=override
    try:
        with TestClient(app) as c:
            c.headers['origin']='http://testserver'
            assert c.get('/api/ai/status').status_code==401
            c.post('/api/session',json={});c.post('/api/demo/connect');drain()
            profile=c.get('/api/templates').json()[0];c.post('/api/templates/'+profile['id']+'/activate')
            id=c.post('/api/products').json()['id']
            image=io.BytesIO();Image.new('RGB',(32,32),'orange').save(image,'PNG')
            c.post(f'/api/products/{id}/images',files=[('files',('test.png',image.getvalue(),'image/png'))])
            with factory() as db:
                saved=db.get(Product,id);saved.description='내가 직접 쓴 설명';saved.material='내가 확인한 소재';db.commit()
            monkeypatch.setattr('app.services.product_service.analyze_product',limit)
            c.post(f'/api/products/{id}/generate');drain()
            p=c.get('/api/products/'+id).json()
            assert p['status']=='AI_WAITING' and p['description']=='내가 직접 쓴 설명' and p['material']=='내가 확인한 소재'
            assert c.get('/api/jobs').json()[0]['status']=='WAITING'
            drain();assert c.get('/api/jobs').json()[0]['status']=='WAITING'
            monkeypatch.setattr('app.services.product_service.analyze_product',lambda p,images,*a: draft(images[0]['id']))
            assert c.post(f'/api/products/{id}/generate').status_code==200;drain()
            p=c.get('/api/products/'+id).json()
            assert p['status']=='NEEDS_INPUT' and p['description']=='내가 직접 쓴 설명'
            assert p['product_name']=='둥근 반지' and p['message']=='' and p['cafe24_product_no'] is None
            statuses=[j['status'] for j in c.get('/api/jobs').json()]
            assert 'WAITING' not in statuses and 'CANCELLED' in statuses
            with factory() as db: assert db.scalar(select(AIGeneration)).model=='codex-subscription'
    finally: app.dependency_overrides.clear()
