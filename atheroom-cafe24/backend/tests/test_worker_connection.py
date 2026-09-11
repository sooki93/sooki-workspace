from datetime import timedelta
from fastapi.testclient import TestClient
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.config import settings
from app.db import Base, get_db
from app.main import app
from app.models import User, WorkerState, Job, now
from app.services.worker_status_service import read_status, record_heartbeat


@pytest.fixture
def database(monkeypatch):
    engine = create_engine('sqlite://', connect_args={'check_same_thread': False}, poolclass=StaticPool)
    Base.metadata.create_all(engine)
    factory = sessionmaker(engine, expire_on_commit=False)
    monkeypatch.setattr('app.main.SessionLocal', factory)
    monkeypatch.setattr(settings, 'demo_mode', True)
    monkeypatch.setattr(settings, 'app_env', 'development')
    monkeypatch.setattr(settings, 'frontend_origin', 'http://testserver')
    def override():
        with factory() as db:
            yield db
    app.dependency_overrides[get_db] = override
    yield factory
    app.dependency_overrides.clear()
    engine.dispose()


def test_offline_queue_is_retained_and_counts_are_private(database):
    with database() as db:
        db.add_all([User(id='owner', email='owner@test'), User(id='other', email='other@test')])
        db.flush()
        db.add_all([Job(user_id='owner', kind='GENERATE', target_id='one'),
                    Job(user_id='other', kind='GENERATE', target_id='two')])
        db.commit()
        status = read_status(db, 'owner')
        assert not status['online'] and not status['ready']
        assert status['queued'] == 1
        record_heartbeat(db, online=True, ai_ready=True)
        assert read_status(db, 'owner')['ready']
        state = db.get(WorkerState, 'primary')
        state.last_seen = now() - timedelta(seconds=46)
        db.commit()
        stale = read_status(db, 'owner')
        assert not stale['ready'] and not stale['online']
        assert stale['queued'] == 1


def test_cloud_reports_mac_login_without_invoking_cloud_cli(database, monkeypatch):
    monkeypatch.setattr(settings, 'execution_host', 'mac')
    monkeypatch.setattr('app.services.codex_service.connection_status', lambda: pytest.fail('Cloud must not launch Codex'))
    with TestClient(app) as client:
        assert client.get('/api/worker/status').status_code == 401
        assert client.get('/api/ai/status').status_code == 401
        client.headers['origin'] = 'http://testserver'
        assert client.post('/api/session', json={}).status_code == 200
        assert client.get('/api/worker/status').json()['enabled']
        assert not client.get('/api/ai/status').json()['ready']
        with database() as db:
            record_heartbeat(db, online=True, ai_ready=False, message='Codex 로그인을 확인해주세요.')
        assert client.get('/api/ai/status').json()['message'] == 'Codex 로그인을 확인해주세요.'
        with database() as db:
            record_heartbeat(db, online=True, ai_ready=True)
        assert client.get('/api/ai/status').json()['ready']
        with database() as db:
            record_heartbeat(db, online=False)
        assert not client.get('/api/worker/status').json()['online']


def test_local_workspace_does_not_show_cloud_waiting_message(database, monkeypatch):
    monkeypatch.setattr(settings, 'execution_host', 'local')
    with TestClient(app) as client:
        client.headers['origin'] = 'http://testserver'
        client.post('/api/session', json={})
        assert client.get('/api/worker/status').json() == {'enabled': False}
