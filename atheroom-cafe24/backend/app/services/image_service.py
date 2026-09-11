import hashlib, io, base64
from pathlib import Path
from PIL import Image, ImageOps, UnidentifiedImageError
import imagehash, boto3
from botocore.config import Config
from app.config import settings
MAX_BYTES=5*1024*1024
Image.MAX_IMAGE_PIXELS=30_000_000

def process_image(raw):
    if len(raw)>MAX_BYTES: raise ValueError('사진 한 장은 5MB 이하로 올려주세요.')
    try:
        with Image.open(io.BytesIO(raw)) as im:
            if im.format not in ('JPEG','PNG','WEBP'): raise ValueError('JPG, PNG, WEBP 사진만 올릴 수 있습니다.')
            im.load(); im=ImageOps.exif_transpose(im).convert('RGB')
            phash=str(imagehash.phash(im)); im.thumbnail((2400,2400))
            output=io.BytesIO(); im.save(output,format='JPEG',quality=90)
            # Private previews still pass through Vercel. Keep converted media below
            # its response limit while direct uploads retain the 5 MB input allowance.
            if output.tell()>4*1024*1024:
                output=io.BytesIO();im.save(output,format='JPEG',quality=80)
    except (UnidentifiedImageError,OSError,Image.DecompressionBombError) as exc: raise ValueError('사진 파일을 확인해주세요.') from exc
    return output.getvalue(),hashlib.sha256(raw).hexdigest(),phash

def s3():
    return boto3.client('s3',endpoint_url=settings.s3_endpoint_url or None,region_name=settings.s3_region,aws_access_key_id=settings.s3_access_key_id or None,aws_secret_access_key=settings.s3_secret_access_key or None,config=Config(s3={'addressing_style':settings.s3_addressing_style}))
def put(key,data):
    if settings.storage_backend=='s3': s3().put_object(Bucket=settings.s3_bucket,Key=key,Body=data,ContentType='image/jpeg',ServerSideEncryption='AES256' if not settings.s3_endpoint_url else None) if not settings.s3_endpoint_url else s3().put_object(Bucket=settings.s3_bucket,Key=key,Body=data,ContentType='image/jpeg')
    else:
        path=Path(settings.upload_dir)/key; path.parent.mkdir(parents=True,exist_ok=True); path.write_bytes(data)
def get(key):
    if '..' in key or key.startswith('/'): raise ValueError('Invalid key')
    if settings.storage_backend=='s3': return s3().get_object(Bucket=settings.s3_bucket,Key=key)['Body'].read(MAX_BYTES+1)
    return (Path(settings.upload_dir)/key).read_bytes()
def remove(key):
    if settings.storage_backend=='s3': s3().delete_object(Bucket=settings.s3_bucket,Key=key)
    else: (Path(settings.upload_dir)/key).unlink(missing_ok=True)
def data_url(key): return 'data:image/jpeg;base64,'+base64.b64encode(get(key)).decode()
def encoded(key): return base64.b64encode(get(key)).decode()
