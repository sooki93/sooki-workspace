import secrets, time, logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
import httpx
from fastapi import FastAPI, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse, RedirectResponse
from fastapi.exceptions import RequestValidationError
from pydantic import BaseModel
from sqlalchemy import select, delete
from app.config import settings
from app.db import Base, engine, SessionLocal, get_db
from app.models import User, LoginSession, OAuthState, Cafe24Account, BrandSettings, Job
from app.security import current_user, admin, digest, utc, verify_password
from app.services.cafe24_service import auth_url, exchange_token, store_tokens, RemoteFailure

@asynccontextmanager
async def lifespan(app):
    settings.validate_runtime()
    if settings.app_env != 'production': Base.metadata.create_all(engine)
    with SessionLocal() as db:
        user=db.scalar(select(User).where(User.email == settings.operator_email))
        if not user:
            user=User(email=settings.operator_email); db.add(user); db.flush()
            db.add(BrandSettings(user_id=user.id, rules={'require_material':True,'require_size':True,'priority':'admin','forbidden':['은은한','자연스럽게 어우러지는','실루엣','세련된 무드','단정한 무드','포인트가 되어','데일리하게','잔잔한','유연하게','룩의 완성도','자연스럽게 아울린다']}))
        db.commit()
    yield
app=FastAPI(title='Attheroom Studio',lifespan=lifespan, docs_url='/docs' if settings.app_env == 'development' else None, redoc_url=None, openapi_url='/openapi.json' if settings.app_env == 'development' else None)
@app.middleware('http')
async def boundary(request, call_next):
    if settings.bridge_token and not secrets.compare_digest(request.headers.get('x-studio-bridge',''),settings.bridge_token):
        return JSONResponse({'detail':'접속 경로를 확인해주세요.'},403)
    if request.method not in ('GET','HEAD','OPTIONS') and request.headers.get('origin') != settings.frontend_origin:
        return JSONResponse({'detail':'접속 경로를 확인한 후 다시 시도해주세요.'},403)
    r=await call_next(request)
    r.headers['X-Content-Type-Options']='nosniff'
    r.headers['Referrer-Policy']='no-referrer'
    r.headers['Cache-Control']='no-store'
    return r
@app.exception_handler(RemoteFailure)
async def remote_error(request, exc): return JSONResponse({'detail':str(exc)},503)
@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    issue=exc.errors()[0] if exc.errors() else {}
    location=issue.get('loc',())
    field=location[1] if len(location)>1 else ''
    labels={'price':'판매가','supply_price':'공급가','product_name':'상품명','description':'상품 설명','material':'소재','size':'사이즈','cafe24_category_id':'쇼핑몰 카테고리','internal_product_group':'상품군','keywords':'검색 키워드','option_settings':'옵션 값'}
    if field in ('price','supply_price'):
        message=labels[field]+'를 확인해주세요. 0원 이상의 정수를 입력하고 금액이 너무 크지 않은지 확인해주세요.'
    elif field=='files': message='업로드할 사진을 선택해주세요.'
    elif field in labels: message=labels[field]+' 입력 내용을 확인해주세요.'
    else: message='입력 내용을 확인해주세요. 숫자와 필수 항목을 올바르게 입력해주세요.'
    return JSONResponse({'detail':message},422)
@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    logging.error('Request failed: %s',type(exc).__name__)
    return JSONResponse({'detail':'처리 중 문제가 발생했습니다. 잠시 후 다시 시도해주세요.'},500)
@app.get('/health')
def health(): return {'ok':True,'service':'attheroom-studio'}
class Login(BaseModel):
    email: str = ''
    password: str = ''
login_attempts={}
@app.post('/api/session')
def login(body:Login, request:Request, response:Response, db=Depends(get_db)):
    key=request.client.host if request.client else 'local'
    attempts=[t for t in login_attempts.get(key,[]) if time.time()-t<300]
    if len(attempts)>=10: raise HTTPException(429,'잠시 후 다시 로그인해주세요.')
    if not settings.demo_mode and (body.email!=settings.operator_email or not verify_password(body.password,settings.operator_password_hash)):
        login_attempts[key]=attempts+[time.time()]; raise HTTPException(401,'이메일과 비밀번호를 확인해주세요.')
    user=db.scalar(select(User).where(User.email==settings.operator_email))
    token=secrets.token_urlsafe(32)
    db.add(LoginSession(id=digest(token),user_id=user.id,expires_at=datetime.now(timezone.utc)+timedelta(hours=12))); db.commit()
    response.set_cookie('studio_session',token,httponly=True,secure=settings.app_env in ('production','mac'),samesite='lax',max_age=43200)
    return {'ok':True}
@app.delete('/api/session')
def logout(request:Request,response:Response,db=Depends(get_db)):
    db.execute(delete(LoginSession).where(LoginSession.id==digest(request.cookies.get('studio_session','')))); db.commit()
    response.delete_cookie('studio_session'); return {'ok':True}
@app.get('/api/public-settings')
def public_settings(): return {'demo':settings.demo_mode}
@app.get('/api/me')
def me(user=Depends(current_user),db=Depends(get_db)):
    account=db.scalar(select(Cafe24Account).where(Cafe24Account.user_id==user.id))
    return {'email':user.email,'role':user.role,'demo':settings.demo_mode,'connected':bool(account),'mall_name':'체험 쇼핑몰' if account and account.demo else (account.mall_id if account else ''),'ai_provider':settings.ai_provider,'demo_ai_enabled':settings.demo_ai_enabled}
@app.get('/api/cafe24/connect')
def connect(request:Request,user=Depends(admin),db=Depends(get_db)):
    state=secrets.token_urlsafe(32); url=auth_url(state)
    db.add(OAuthState(id=digest(state),user_id=user.id,session_hash=digest(request.cookies.get('studio_session','')),expires_at=datetime.now(timezone.utc)+timedelta(minutes=5))); db.commit()
    return RedirectResponse(url)
@app.get('/api/cafe24/callback')
def callback(request:Request,state:str='',code:str='',error:str='',user=Depends(admin),db=Depends(get_db)):
    if settings.demo_mode: raise HTTPException(400,'체험 모드에서는 실제 쇼핑몰을 연결하지 않습니다.')
    record=db.scalar(select(OAuthState).where(OAuthState.id==digest(state)).with_for_update())
    if not record or record.user_id!=user.id or record.session_hash!=digest(request.cookies.get('studio_session','')) or utc(record.expires_at)<datetime.now(timezone.utc):
        raise HTTPException(400,'연결 승인이 만료되었습니다. 다시 연결해주세요.')
    consumed=db.execute(delete(OAuthState).where(OAuthState.id==record.id))
    if consumed.rowcount!=1: raise HTTPException(400,'이미 사용된 연결 승인입니다. 다시 연결해주세요.')
    db.commit()
    if error or not code: return RedirectResponse(settings.frontend_origin+'/?connection=cancelled')
    with httpx.Client(timeout=30) as client:
        data=exchange_token(settings.cafe24_mall_id,{'grant_type':'authorization_code','code':code,'redirect_uri':settings.cafe24_redirect_uri},client)
    account=db.scalar(select(Cafe24Account).where(Cafe24Account.user_id==user.id))
    initial=not account
    if not account: account=Cafe24Account(user_id=user.id,mall_id=settings.cafe24_mall_id); db.add(account)
    store_tokens(account,data)
    if initial:
        db.add(Job(user_id=user.id,kind='ANALYZE'))
        db.add(Job(user_id=user.id,kind='INDEX'))
    db.commit(); return RedirectResponse(settings.frontend_origin+'/?connected=1')
from app.api.templates import router as templates_router
app.include_router(templates_router)
from app.api.uploads import router as uploads_router
app.include_router(uploads_router)
from app.api.products import router as products_router
from app.api.settings import router as settings_router
app.include_router(products_router)
app.include_router(settings_router)
from app.api.publishing import router as publishing_router
app.include_router(publishing_router)
