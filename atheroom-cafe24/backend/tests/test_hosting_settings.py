import pytest
from pydantic import ValidationError
from app.config import Settings, settings
from app.services import image_service


@pytest.mark.parametrize('scheme', ['postgres', 'postgresql', 'postgresql+psycopg'])
def test_hosting_database_url_uses_available_driver_without_changing_credentials(scheme):
    tail = 'studio:p%40ss%3Aword@postgres.railway.internal:5432/studio?sslmode=require'
    config = Settings(_env_file=None, database_url=scheme + '://' + tail)
    assert config.database_url == 'postgresql+psycopg://' + tail


def test_local_demo_url_is_unchanged():
    assert Settings(_env_file=None, database_url='sqlite:///./studio.db').database_url == 'sqlite:///./studio.db'


def test_s3_bucket_uses_configured_address_style(monkeypatch):
    monkeypatch.setattr(settings, 's3_endpoint_url', 'https://storage.example.test')
    monkeypatch.setattr(settings, 's3_region', 'auto')
    monkeypatch.setattr(settings, 's3_access_key_id', 'test-only')
    monkeypatch.setattr(settings, 's3_secret_access_key', 'test-only')
    monkeypatch.setattr(settings, 's3_addressing_style', 'virtual')
    client = image_service.s3()
    try:
        # Signing is local only: verifies boto3 actually addresses the bucket as a host.
        url = client.generate_presigned_url('get_object', Params={'Bucket': 'studio-photos', 'Key': 'photo.jpg'})
        assert url.startswith('https://studio-photos.storage.example.test/photo.jpg?')
    finally:
        client.close()


def test_invalid_s3_address_style_is_rejected():
    with pytest.raises(ValidationError):
        Settings(_env_file=None, s3_addressing_style='unsupported')
