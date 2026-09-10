"""Optional real-PostgreSQL checks, isolated in a fresh schema per test.
Run with TEST_POSTGRES_URL pointed at a disposable local test database.
"""
import os
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, text, select
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError
from app.models import User, TemplateProfile
from app.services.template_analysis_service import build_profile
from app.api.templates import activate


@pytest.fixture
def postgres_engine(monkeypatch):
    url = os.getenv('TEST_POSTGRES_URL')
    if not url:
        pytest.skip('TEST_POSTGRES_URL is not configured')
    assert url.startswith('postgresql'), 'Use a PostgreSQL test database'
    schema = 'qa_' + uuid.uuid4().hex
    admin_engine = create_engine(url)
    with admin_engine.begin() as c:
        c.execute(text(f'CREATE SCHEMA {schema}'))
    engine = create_engine(url, connect_args={'options': '-csearch_path=' + schema})
    try:
        # Run the actual migration against this isolated schema.
        monkeypatch.setattr('app.db.engine', engine)
        config = Config()
        config.set_main_option('script_location', str(Path(__file__).parents[1] / 'migrations'))
        command.upgrade(config, 'head')
        yield engine
    finally:
        engine.dispose()
        with admin_engine.begin() as c:
            c.execute(text(f'DROP SCHEMA {schema} CASCADE'))
        admin_engine.dispose()


def test_operator_flow_on_postgresql(postgres_engine, tmp_path, monkeypatch):
    import test_end_to_end as flow
    monkeypatch.setattr(flow, 'create_engine', lambda *args, **kwargs: postgres_engine)
    flow.test_complete_operator_flow(tmp_path, monkeypatch)


def test_concurrent_template_activation_keeps_one_active(postgres_engine):
    with Session(postgres_engine, expire_on_commit=False) as db:
        user = User(email='postgres-qa@example.com')
        db.add(user)
        db.commit()
        user_id = user.id
        first = build_profile(db, user_id, demo=True)
        second = build_profile(db, user_id, demo=True)
        ids = [first.id, second.id]
    def approve(profile_id):
        with Session(postgres_engine) as db:
            return activate(profile_id, db.get(User, user_id), db)['status']
    with ThreadPoolExecutor(max_workers=2) as pool:
        assert list(pool.map(approve, ids)) == ['ACTIVE', 'ACTIVE']
    with Session(postgres_engine) as db:
        profiles = list(db.scalars(select(TemplateProfile).where(TemplateProfile.user_id == user_id)))
        assert sorted(p.status for p in profiles) == ['ACTIVE', 'ARCHIVED']
        db.add(TemplateProfile(user_id=user_id, mall_id='demo', version=3, status='ACTIVE'))
        with pytest.raises(IntegrityError):
            db.commit()
