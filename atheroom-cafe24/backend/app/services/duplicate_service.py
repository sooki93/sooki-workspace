import re,logging
from difflib import SequenceMatcher
from sqlalchemy import select
from app.config import settings
from app.models import Product,SourceProduct,Cafe24Account
from app.services.product_service import images_for
from app.services.cafe24_service import Cafe24Service,RemoteFailure
from app.services.html_parser_service import infer_group
from app.services.image_service import process_image
from app.services.safe_fetch import fetch_image

def name_similarity(a,b):
    normalize=lambda x:re.sub(r'[^가-힣a-z0-9]','',x.lower())
    return SequenceMatcher(None,normalize(a),normalize(b)).ratio() if a and b else 0

def hash_reasons(images,hashes):
    reasons=[]
    if any(i.file_hash==h.get('sha') for i in images for h in hashes): reasons.append('동일한 사진')
    if any((int(i.perceptual_hash,16)^int(h['phash'],16)).bit_count()<=6 for i in images for h in hashes if h.get('phash')): reasons.append('유사한 사진')
    return reasons

def sync_catalogue(db,user_id):
    service=Cafe24Service(db,user_id)
    if service.account.demo: service.close();return
    since=0;seen=set()
    try:
        # This is a duplicate index only: no HTML parsing or template/AI analysis.
        for _ in range(1000):
            rows=service.request('GET','/products',params={'since_product_no':since,'limit':100,'fields':'product_no,product_name,created_date,detail_image'})['products']
            if not rows: break
            next_since=max(int(r['product_no']) for r in rows)
            if next_since<=since: raise RemoteFailure('기존 상품 목록을 모두 확인하지 못했습니다. 다시 시도해주세요.')
            for row in rows:
                number=int(row['product_no']);seen.add(number)
                source=db.scalar(select(SourceProduct).where(SourceProduct.user_id==user_id,SourceProduct.product_no==number))
                if not source:
                    source=SourceProduct(user_id=user_id,product_no=number,product_name=row['product_name'],product_group=infer_group(row['product_name']),created_date=row['created_date']); db.add(source)
                thumbnail=row.get('detail_image') or ''
                if thumbnail and (source.thumbnail!=thumbnail or not source.image_hashes):
                    try:
                        _,sha,phash=process_image(fetch_image(thumbnail));source.image_hashes=[{'sha':sha,'phash':phash}]
                    except Exception as exc:
                        source.image_hashes=[];logging.warning('duplicate_image_unavailable product=%s type=%s',number,type(exc).__name__)
                source.product_name=row['product_name'];source.thumbnail=thumbnail
            db.commit();since=next_since
            if len(rows)<100: break
        else: raise RemoteFailure('상품 수가 많아 비교를 마치지 못했습니다. 운영 담당자에게 문의해주세요.')
        # Remove deleted catalogue entries only if the complete scan succeeded.
        for source in db.scalars(select(SourceProduct).where(SourceProduct.user_id==user_id)):
            if source.product_no not in seen: db.delete(source)
        db.commit()
    finally: service.close()

def duplicates(db,p):
    images=images_for(db,p);result=[]
    account=db.scalar(select(Cafe24Account).where(Cafe24Account.user_id==p.user_id))
    for other in db.scalars(select(Product).where(Product.user_id==p.user_id,Product.id!=p.id,Product.status.in_(['UPLOADED','PARTIAL_FAILED']))):
        reasons=hash_reasons(images,[{'sha':i.file_hash,'phash':i.perceptual_hash} for i in images_for(db,other)])
        if name_similarity(p.product_name,other.product_name)>=.88: reasons.append('비슷한 상품명')
        if reasons: result.append({'name':other.product_name,'reasons':reasons,'url':remote_url(account,other.cafe24_product_no) if not account.demo else None})
    coverage_incomplete=False
    for source in db.scalars(select(SourceProduct).where(SourceProduct.user_id==p.user_id)):
        if source.product_no==p.cafe24_product_no: continue
        if source.thumbnail and not source.image_hashes: coverage_incomplete=True
        reasons=hash_reasons(images,source.image_hashes)
        if name_similarity(p.product_name,source.product_name)>=.88: reasons.append('비슷한 상품명')
        if reasons: result.append({'name':source.product_name,'reasons':reasons,'url':remote_url(account,source.product_no) if not account.demo else None})
    if coverage_incomplete: result.append({'name':'일부 기존 사진을 비교하지 못했습니다.','reasons':['쇼핑몰에서 유사한 상품이 없는지 확인해주세요.'],'url':f'https://{account.mall_id}.cafe24.com' if not account.demo else None})
    return result

def remote_url(account,number):
    return f'https://{account.mall_id}.cafe24.com/disp/admin/shop{settings.cafe24_shop_no}/product/ProductRegister?product_no={number}'
