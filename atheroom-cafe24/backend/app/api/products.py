from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db import get_db
from app.security import current_user
from app.models import Product,Job,TemplateProfile
from app.services.product_service import owned,editable,touch,images_for,image_dict,choose_template,refresh_preview,missing,review_issues,allowed_image_types
from app.schemas.product import ProductEdit,Review
router=APIRouter(prefix='/api/products')

def serialize(db,p):
    keys=('id','status','revision','reviewed_revision','product_name','price','supply_price','internal_product_group','cafe24_category_id','description','material','size','keywords','seo','ai_result','main_image_id','reference_product_id','template_profile_id','rendered_html','warnings','cafe24_product_no','upload_steps','message','created_at')
    return {k:getattr(p,k) for k in keys}|{'images':[image_dict(i) for i in images_for(db,p)],'missing_fields':missing(db,p),'review_issues':review_issues(db,p),'allowed_image_types':allowed_image_types(p),'main_photo_has_own_section':any(i['type']=='MAIN_CANDIDATE' for i in p.template_snapshot.get('images',[]))}
@router.get('')
def products(user=Depends(current_user),db=Depends(get_db)):
    return [serialize(db,p) for p in db.scalars(select(Product).where(Product.user_id==user.id).order_by(Product.created_at.desc()))]
@router.post('')
def create(user=Depends(current_user),db=Depends(get_db)):
    p=Product(user_id=user.id); db.add(p); db.commit(); return serialize(db,p)
@router.get('/{id}')
def get_product(id:str,user=Depends(current_user),db=Depends(get_db)): return serialize(db,owned(db,user.id,id))
@router.put('/{id}')
def edit(id:str,body:ProductEdit,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id,True); editable(p,body.revision)
    if body.main_image_id and body.main_image_id not in {i.id for i in images_for(db,p)}: raise HTTPException(400,'대표 이미지를 다시 선택해주세요.')
    manual=set(p.ai_result.get('manual_fields',[]))
    for key in ('product_name','description','keywords','seo_title','seo_description'):
        previous=p.seo.get(key[4:],'') if key.startswith('seo_') else getattr(p,key)
        value=getattr(body,key)
        if value!=previous:
            if value: manual.add(key)
            else: manual.discard(key)
    for key,value in body.model_dump(exclude={'revision','seo_title','seo_description'}).items(): setattr(p,key,value)
    p.internal_product_group=body.internal_product_group.value
    p.seo={'title':body.seo_title,'description':body.seo_description}
    p.ai_result={**p.ai_result,'group_confirmed':True,'manual_fields':sorted(manual)}
    if p.template_profile_id: choose_template(db,p)
    touch(p); refresh_preview(db,p); db.commit(); return serialize(db,p)
@router.post('/{id}/generate')
def generate(id:str,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id,True); editable(p)
    if not images_for(db,p): raise HTTPException(400,'먼저 상품 사진을 올려주세요.')
    if not db.scalar(select(TemplateProfile).where(TemplateProfile.user_id==user.id,TemplateProfile.status=='ACTIVE')): raise HTTPException(400,'기존 상품 형식을 먼저 승인해주세요.')
    p.status='AI_GENERATING'; p.reviewed_revision=None
    job=Job(user_id=user.id,target_id=p.id,kind='GENERATE'); db.add(job); db.commit(); return {'job_id':job.id}
@router.post('/{id}/fit')
def fit(id:str,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id,True); editable(p); choose_template(db,p); touch(p); refresh_preview(db,p); db.commit(); return serialize(db,p)
@router.post('/{id}/review')
def review(id:str,body:Review,user=Depends(current_user),db=Depends(get_db)):
    p=owned(db,user.id,id,True); editable(p,body.revision)
    choose_template(db,p); refresh_preview(db,p)
    required=missing(db,p)
    if required: raise HTTPException(400,' '.join(required))
    if p.warnings and not body.acknowledge_warnings: raise HTTPException(400,'기존 상품 형식과 다른 부분을 확인해주세요.')
    p.status='REVIEWED'; p.reviewed_revision=p.revision; db.commit(); return serialize(db,p)
