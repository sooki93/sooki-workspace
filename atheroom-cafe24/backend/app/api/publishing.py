from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select,update
from app.db import get_db
from app.security import current_user
from app.models import Product,Job,Cafe24Account,TemplateProfile
from app.schemas.product import Publish
from app.services.product_service import owned,missing
from app.services.duplicate_service import duplicates,sync_catalogue,remote_url
router=APIRouter(prefix='/api/products')
@router.get('/{id}/duplicates')
def check(id:str,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id)
    return duplicates(db,p)
@router.post('/{id}/publish')
def publish(id:str,body:Publish,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id,True)
    if p.status=='UPLOADED': return {'ok':True}
    if p.status!='REVIEWED' or p.revision!=body.revision or p.reviewed_revision!=p.revision: raise HTTPException(409,'내용을 다시 확인하고 검수를 완료해주세요.')
    active=db.scalar(select(TemplateProfile).where(TemplateProfile.user_id==user.id,TemplateProfile.status=='ACTIVE'))
    if not active or p.template_profile_id!=active.id: raise HTTPException(409,'사용 중인 상품 형식이 바뀌었습니다. 기존 형식에 맞추기를 누른 뒤 다시 검수해주세요.')
    required=missing(db,p)
    if required: raise HTTPException(400,' '.join(required))
    if duplicates(db,p) and not body.allow_duplicate: raise HTTPException(409,'비슷한 상품이 있습니다. 확인 후 다시 등록해주세요.')
    p.upload_steps={**p.upload_steps,'approval':{'status':'DONE','allow_duplicate':body.allow_duplicate,'revision':p.revision}}
    p.status='UPLOADING';p.message='등록을 준비하고 있습니다.'
    job=Job(user_id=user.id,target_id=p.id,kind='PUBLISH');db.add(job);db.commit();return {'job_id':job.id}
@router.post('/{id}/retry')
def retry(id:str,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id,True)
    if p.status not in ('FAILED','PARTIAL_FAILED') or not p.upload_steps.get('create'): raise HTTPException(400,'다시 등록할 단계를 확인해주세요.')
    if p.reviewed_revision!=p.revision: raise HTTPException(409,'상품 내용을 다시 검수해주세요.')
    p.status='UPLOADING';job=Job(user_id=user.id,target_id=p.id,kind='PUBLISH');db.add(job);db.commit();return {'job_id':job.id}
@router.get('/{id}/remote-url')
def url(id:str,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id);account=db.scalar(select(Cafe24Account).where(Cafe24Account.user_id==user.id))
    if not account or account.demo or not p.cafe24_product_no: raise HTTPException(400,'실제 등록된 상품이 없습니다.')
    return {'url':remote_url(account,p.cafe24_product_no)}
