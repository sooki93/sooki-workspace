import pytest
from app.config import Settings, settings


def valid(**overrides):
    config = dict(app_env='mac', demo_mode=False, database_url='sqlite:///private.db',
        storage_backend='local', operator_password_hash='provisioned', token_encryption_key='provisioned',
        bridge_token='x'*48, frontend_origin='https://studio.example.test', ai_provider='codex')
    config.update(overrides)
    return Settings(_env_file=None, **config)


def test_personal_mac_allows_local_storage_without_paid_api():
    valid().validate_runtime()


@pytest.mark.parametrize('changes',[{'demo_mode':True},{'bridge_token':''},
    {'operator_password_hash':''},{'token_encryption_key':''},{'openai_api_key':'accidental-key'},
    {'ai_provider':'openai'},{'frontend_origin':'http://localhost'},{'storage_backend':'s3'}])
def test_mac_public_tunnel_fails_closed_on_insecure_configuration(changes):
    with pytest.raises(RuntimeError): valid(**changes).validate_runtime()


def test_bridge_does_not_replace_user_login(monkeypatch):
    from fastapi.testclient import TestClient
    from app.main import app
    monkeypatch.setattr(settings, 'bridge_token', 'x'*48)
    # Do not run lifespan or touch the real database. The auth dependency returns 401
    # before DB access when there is no session cookie.
    client=TestClient(app)
    assert client.get('/api/public-settings').status_code==403
    assert client.get('/api/public-settings',headers={'x-studio-bridge':'wrong'}).status_code==403
    assert client.get('/api/public-settings',headers={'x-studio-bridge':'x'*48}).status_code==200
    assert client.get('/api/me',headers={'x-studio-bridge':'x'*48}).status_code==401
    assert client.post('/api/session',headers={'x-studio-bridge':'x'*48,'origin':'https://attacker.example'},json={}).status_code==403
