from app.services.duplicate_service import name_similarity,hash_reasons
from app.services.safe_fetch import fetch_image
from types import SimpleNamespace
import pytest

def test_duplicate_detection():
    assert name_similarity('반지 A','반지-A')==1
    i=SimpleNamespace(file_hash='sha',perceptual_hash='0'*16)
    assert hash_reasons([i],[{'sha':'sha','phash':'0'*15+'1'}])==['동일한 사진','유사한 사진']
    assert not hash_reasons([i],[{'sha':'different','phash':'f'*16}])
def test_remote_images_cannot_reach_private_network():
    for url in ('https://127.0.0.1/private','http://example.com/a.jpg','https://localhost/a.jpg','https://user:pass@example.com/a.jpg'):
        with pytest.raises(ValueError): fetch_image(url)
