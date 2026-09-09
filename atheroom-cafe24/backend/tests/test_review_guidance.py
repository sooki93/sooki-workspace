import io
import pytest
from PIL import Image
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.pool import StaticPool
from sqlalchemy.orm import sessionmaker
from app.db import Base, get_db
from app.models import Job, Product
from app.main import app
from app.worker import execute
from app.config import settings


@pytest.fixture
def draft(tmp_path, monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    factory = sessionmaker(engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    monkeypatch.setattr('app.main.SessionLocal', factory)
    monkeypatch.setattr(settings, 'upload_dir', str(tmp_path))
    monkeypatch.setattr(settings, 'frontend_origin', 'http://testserver')
    def override():
        with factory() as db:
            yield db
    def drain():
        with factory() as db:
            for job in db.scalars(select(Job).where(Job.status == 'QUEUED')):
                execute(db, job)
    app.dependency_overrides[get_db] = override
    try:
        with TestClient(app) as client:
            client.headers['origin'] = 'http://testserver'
            assert client.post('/api/session', json={}).status_code == 200
            assert client.post('/api/demo/connect').status_code == 200
            drain()
            profile = client.get('/api/templates').json()[0]
            assert client.post('/api/templates/' + profile['id'] + '/activate').status_code == 200
            product_id = client.post('/api/products').json()['id']
            picture = io.BytesIO()
            Image.new('RGB', (50, 50), 'orange').save(picture, 'PNG')
            assert client.post(f'/api/products/{product_id}/images', files=[('files', (f'{i}.png', picture.getvalue(), 'image/png')) for i in range(3)]).status_code == 200
            assert client.post(f'/api/products/{product_id}/generate').status_code == 200
            drain()
            # Start with all required facts supplied, but no photo/group confirmation.
            with factory() as db:
                p = db.get(Product, product_id)
                p.product_name = '확인용 목걸이'
                p.price = 10000
                p.supply_price = 5000
                p.material = '직접 확인한 소재'
                p.size = '직접 확인한 치수'
                p.cafe24_category_id = 42
                db.commit()
            yield client, product_id, drain
    finally:
        app.dependency_overrides.clear()
        engine.dispose()


def confirm_group(client, product_id):
    p = client.get('/api/products/' + product_id).json()
    payload = {key: p[key] for key in ('revision', 'product_name', 'price', 'supply_price', 'internal_product_group', 'cafe24_category_id', 'description', 'material', 'size', 'keywords', 'main_image_id', 'reference_product_id')}
    response = client.put('/api/products/' + product_id, json=payload)
    assert response.status_code == 200, response.text
    return response.json()


def classify(client, product_id, role='WEARING'):
    p = client.get('/api/products/' + product_id).json()
    response = client.put(f'/api/products/{product_id}/images', json={'revision': p['revision'], 'main_image_id': p['main_image_id'], 'images': [{'id': i['id'], 'image_type': 'ETC' if i['id'] == p['main_image_id'] else role, 'confirmed': True} for i in p['images']]})
    assert response.status_code == 200, response.text
    return client.get('/api/products/' + product_id).json()


def test_acknowledging_differences_does_not_confirm_photos_or_group(draft):
    client, product_id, _ = draft
    p = client.get('/api/products/' + product_id).json()
    issues = p['review_issues']
    assert [i['code'] for i in issues] == ['image_unclassified', 'image_unclassified', 'group_unconfirmed']
    assert all(i['image_id'] != p['main_image_id'] for i in issues)
    assert issues[0]['target'] == 'photo-' + p['images'][1]['id']
    assert p['allowed_image_types'] == ['WEARING', 'PRODUCT', 'DETAIL']
    response = client.post(f'/api/products/{product_id}/review', json={'revision': p['revision'], 'acknowledge_warnings': True})
    assert response.status_code == 400
    assert '사진 2' in response.json()['detail']
    assert client.get('/api/products/' + product_id).json()['status'] != 'REVIEWED'


def test_same_group_confirmation_and_fewer_photos_can_complete_review(draft):
    client, product_id, _ = draft
    p = confirm_group(client, product_id)
    assert not any(i['code'] == 'group_unconfirmed' for i in p['review_issues'])
    p = classify(client, product_id)
    assert not p['missing_fields']
    assert p['warnings']  # Fewer wearing/product/detail photos than original format.
    assert client.post(f'/api/products/{product_id}/publish', json={'revision': p['revision']}).status_code == 409
    assert client.post(f'/api/products/{product_id}/review', json={'revision': p['revision']}).status_code == 400
    response = client.post(f'/api/products/{product_id}/review', json={'revision': p['revision'], 'acknowledge_warnings': True})
    assert response.status_code == 200, response.text
    assert response.json()['status'] == 'REVIEWED'
    assert response.json()['reviewed_revision'] == p['revision']
    assert client.post(f'/api/products/{product_id}/publish', json={'revision': p['revision']}).status_code == 200


def test_unclassified_photo_cannot_be_confirmed(draft):
    client, product_id, _ = draft
    p = classify(client, product_id, 'ETC')
    assert all(not i['confirmed'] for i in p['images'])
    assert sum(i['code'] == 'image_unclassified' for i in p['review_issues']) == 2


def test_regeneration_preserves_confirmed_group_photos_and_order(draft):
    client, product_id, drain = draft
    confirm_group(client, product_id)
    p = classify(client, product_id)
    photos = list(reversed(p['images']))
    assert client.put(f'/api/products/{product_id}/images', json={'revision': p['revision'], 'main_image_id': p['main_image_id'], 'images': [{'id': i['id'], 'image_type': i['image_type'], 'confirmed': i['confirmed']} for i in photos]}).status_code == 200
    assert client.post(f'/api/products/{product_id}/generate').status_code == 200
    drain()
    result = client.get('/api/products/' + product_id).json()
    assert result['ai_result']['group_confirmed'] is True
    assert result['internal_product_group'] == p['internal_product_group']
    assert result['cafe24_category_id'] == p['cafe24_category_id']
    assert [i['id'] for i in result['images']] == [i['id'] for i in photos]
    assert all(i['confirmed'] and i['image_type'] == 'WEARING' for i in result['images'] if i['id'] != p['main_image_id'])
    assert not result['missing_fields']
