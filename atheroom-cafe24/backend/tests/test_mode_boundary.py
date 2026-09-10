import pytest
from types import SimpleNamespace
from app.config import settings
from app.services.cafe24_service import Cafe24Service, RemoteFailure


def test_demo_mode_blocks_real_commerce_before_reading_tokens(monkeypatch):
    monkeypatch.setattr(settings, 'demo_mode', True)
    service = object.__new__(Cafe24Service)
    service.account = SimpleNamespace(demo=False)
    service.token = lambda: pytest.fail('A token must not be read in demo mode')
    with pytest.raises(RemoteFailure, match='체험 모드'):
        service.request('POST', '/products', payload={})
