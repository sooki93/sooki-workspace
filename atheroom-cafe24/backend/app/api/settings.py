from fastapi import APIRouter,Depends,HTTPException
from pydantic import BaseModel,Field,ConfigDict
from sqlalchemy import select
from app.db import get_db
from app.security import current_user,admin
from app.models import BrandSettings,Cafe24Account,Job
from app.schemas.ai import Group
from app.config import settings
from app.services.cafe24_service import Cafe24Service
router=APIRouter(prefix='/api')
@router.get('/ai/status')
def ai_status(user=Depends(admin),db=Depends(get_db)):
    if settings.execution_host == 'mac':
        from app.services.worker_status_service import read_status
        return {'provider':settings.ai_provider, **read_status(db,user.id)}
    if settings.ai_provider == 'codex':
        from app.services.codex_service import connection_status
        return {'provider':'codex', **connection_status()}
    return {'provider':'openai','ready':bool(settings.openai_api_key),'message':'OpenAI API 방식입니다. API 사용료가 별도로 발생합니다.'}

@router.get('/worker/status')
def worker_status(user=Depends(current_user),db=Depends(get_db)):
    if settings.execution_host != 'mac':
        return {'enabled':False}
    from app.services.worker_status_service import read_status
    return {'enabled':True, **read_status(db,user.id)}

class SettingsEdit(BaseModel):
    model_config=ConfigDict(extra='forbid')
    require_material: bool
    require_size: bool
    priority: str
    forbidden: list[str] = Field(max_length=100)
    name_rules: str = Field(default='',max_length=2000)
    description_rules: str = Field(default='',max_length=2000)
    fixed_notice: str = Field(default='',max_length=5000)
    seo_rules: str = Field(default='',max_length=2000)
    category_mapping: dict[Group,int]
@router.get('/settings')
def read_settings(user=Depends(current_user),db=Depends(get_db)):
    b=db.get(BrandSettings,user.id); return {'rules':b.rules,'category_mapping':b.category_mapping,'categories':b.categories}
@router.put('/settings')
def update_settings(body:SettingsEdit,user=Depends(admin),db=Depends(get_db)):
    if body.priority not in ['admin','analyzed']: raise HTTPException(400,'작성 기준을 선택해주세요.')
    b=db.get(BrandSettings,user.id)
    if any(v not in {c['id'] for c in b.categories} for v in body.category_mapping.values()): raise HTTPException(400,'쇼핑몰 분류를 다시 선택해주세요.')
    b.rules=body.model_dump(exclude={'category_mapping'}); b.category_mapping={k.value:v for k,v in body.category_mapping.items()}; db.commit(); return read_settings(user,db)
@router.post('/settings/categories/refresh')
def refresh_categories(user=Depends(admin),db=Depends(get_db)):
    b=db.get(BrandSettings,user.id); a=db.scalar(select(Cafe24Account).where(Cafe24Account.user_id==user.id))
    if a and not a.demo:
        service=Cafe24Service(db,user.id)
        try: b.categories=[{'id':int(c['category_no']),'name':c['category_name']} for c in service.categories()]
        finally: service.close()
    b.category_mapping={k:v for k,v in b.category_mapping.items() if v in {c['id'] for c in b.categories}}
    db.commit(); return read_settings(user,db)
@router.post('/demo/connect')
def demo_connect(user=Depends(admin),db=Depends(get_db)):
    if not settings.demo_mode: raise HTTPException(404,'사용할 수 없는 기능입니다.')
    if not db.scalar(select(Cafe24Account).where(Cafe24Account.user_id==user.id)):
        db.add(Cafe24Account(user_id=user.id,mall_id='demo',demo=True))
        b=db.get(BrandSettings,user.id)
        labels=['반지','목걸이','귀걸이','팔찌','피어싱','헤어','기타']
        b.categories=[{'id':42+i,'name':label} for i,label in enumerate(labels)]
        b.category_mapping={g.value:42+i for i,g in enumerate(Group)}
        db.add(Job(user_id=user.id,kind='ANALYZE')); db.commit()
    return {'ok':True}
