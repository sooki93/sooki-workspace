from fastapi import APIRouter,Depends,HTTPException
from sqlalchemy import select
from app.db import get_db
from app.models import TemplateProfile,User,Job,Cafe24Account,SourceProduct,now,BrandSettings
from app.security import admin,current_user
from app.services.render_service import render,LABEL
router=APIRouter(prefix='/api')

def display_order(template):
    order=template.get('section_order',[])
    labels=[]; index=0
    while index<len(order):
        if order[index:index+3]==['DESCRIPTION','MATERIAL','SIZE']:
            labels.append('상품 설명 · 소재 · 사이즈 안내'); index+=3
        else:
            labels.append(LABEL.get(order[index],order[index])); index+=1
    return labels

def summary(p):
    return {'id':p.id,'version':p.version,'status':p.status,'analysis':p.analysis,'created_at':p.created_at,'section_order':display_order(p.global_template),'description_rules':p.global_template.get('description_rules',{}),'category_groups':list(p.category_templates),'styles':p.styles,'can_activate':bool(p.global_template) and not p.global_template.get('unresolved'),'preview_html':render(p.global_template,{},[],preview=True)}
@router.get('/templates')
def profiles(user=Depends(current_user),db=Depends(get_db)):
    return [summary(p) for p in db.scalars(select(TemplateProfile).where(TemplateProfile.user_id==user.id).order_by(TemplateProfile.version.desc()))]
@router.post('/templates/analyze')
def reanalyze(user=Depends(admin),db=Depends(get_db)):
    if not db.scalar(select(Cafe24Account).where(Cafe24Account.user_id==user.id)): raise HTTPException(400,'먼저 쇼핑몰을 연결해주세요.')
    running=db.scalar(select(Job).where(Job.user_id==user.id,Job.kind=='ANALYZE',Job.status.in_(['QUEUED','RUNNING'])))
    if running: return {'job_id':running.id}
    for waiting in db.scalars(select(Job).where(Job.user_id==user.id,Job.kind=='ANALYZE',Job.status=='WAITING')):
        waiting.status='CANCELLED'; waiting.message='새 요청으로 다시 시작했습니다.'
    job=Job(user_id=user.id,kind='ANALYZE'); db.add(job); db.commit(); return {'job_id':job.id}
@router.post('/templates/{id}/activate')
def activate(id:str,user=Depends(admin),db=Depends(get_db)):
    db.scalar(select(User).where(User.id==user.id).with_for_update())
    profile=db.scalar(select(TemplateProfile).where(TemplateProfile.id==id,TemplateProfile.user_id==user.id).with_for_update())
    if not profile: raise HTTPException(404,'형식을 찾을 수 없습니다.')
    if profile.status=='ACTIVE': return summary(profile)
    if profile.status!='DRAFT' or not profile.global_template or profile.global_template.get('unresolved'):
        raise HTTPException(400,'반복된 상품 형식과 공통 문구를 확인한 후 적용해주세요.')
    for old in db.scalars(select(TemplateProfile).where(TemplateProfile.user_id==user.id,TemplateProfile.status=='ACTIVE')):
        old.status='ARCHIVED'; old.archived_at=now()
    db.flush(); profile.status='ACTIVE'; profile.activated_at=now(); db.commit(); return summary(profile)
@router.post('/templates/{id}/discard')
def discard(id:str,user=Depends(admin),db=Depends(get_db)):
    p=db.scalar(select(TemplateProfile).where(TemplateProfile.id==id,TemplateProfile.user_id==user.id))
    if not p or p.status!='DRAFT': raise HTTPException(400,'검토 중인 형식만 보관할 수 있습니다.')
    p.status='ARCHIVED'; p.archived_at=now(); db.commit(); return {'ok':True}
@router.get('/references')
def references(user=Depends(current_user),db=Depends(get_db)):
    return [{'id':p.id,'product_no':p.product_no,'name':p.product_name,'group':p.product_group,'thumbnail':p.thumbnail} for p in db.scalars(select(SourceProduct).where(SourceProduct.user_id==user.id).order_by(SourceProduct.created_date.desc())) if p.parsed]
@router.get('/jobs')
def jobs(user=Depends(current_user),db=Depends(get_db)):
    return [{'id':j.id,'kind':j.kind,'target_id':j.target_id,'status':j.status,'message':j.message} for j in db.scalars(select(Job).where(Job.user_id==user.id).order_by(Job.created_at.desc()).limit(20))]
