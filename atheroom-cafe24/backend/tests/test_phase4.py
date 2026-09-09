import io
import pytest
from PIL import Image
from app.services.image_service import process_image
from app.schemas.ai import ProductAnalysis
from pydantic import ValidationError

def test_upload_hashes_and_real_file_validation():
    b=io.BytesIO(); Image.new('RGB',(32,32),'red').save(b,'PNG'); raw=b.getvalue()
    converted,sha,phash=process_image(raw)
    assert len(sha)==64 and len(phash)==16 and converted.startswith(b'\xff\xd8')
    with pytest.raises(ValueError): process_image(b'<svg onload="alert(1)"></svg>')
    with pytest.raises(ValueError): process_image(b'x'*(5*1024*1024+1))
def test_ai_cannot_return_commercial_facts():
    with pytest.raises(ValidationError): ProductAnalysis.model_validate({'price':10000,'material':'silver'})
