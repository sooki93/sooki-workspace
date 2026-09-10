"""Durable single-consumer worker. PostgreSQL advisory lock prevents competing workers."""
import time,logging,signal,fcntl
from sqlalchemy import select,text
from app.db import SessionLocal,engine
from app.models import Job,Product,Cafe24Account,now
from app.services.template_analysis_service import build_profile
from app.services.product_service import generate
from app.services.upload_service import publish_product
from app.services.duplicate_service import sync_catalogue,duplicates
from app.config import settings
stop=False

def execute(db,job):
    account=db.scalar(select(Cafe24Account).where(Cafe24Account.user_id==job.user_id))
    demo=bool(account and account.demo)
    try:
        if not account or account.demo!=settings.demo_mode:
            raise ValueError('현재 실행 모드와 쇼핑몰 연결이 다릅니다. 체험용과 실제 운영용 작업실을 분리해주세요.')
        if job.kind=='ANALYZE': build_profile(db,job.user_id,demo)
        elif job.kind=='INDEX': sync_catalogue(db,job.user_id)
        else:
            p=db.get(Product,job.target_id)
            if not p or p.user_id!=job.user_id: raise ValueError('상품을 찾을 수 없습니다.')
            if job.kind=='GENERATE': generate(db,p,demo)
            elif job.kind=='PUBLISH':
                if not p.cafe24_product_no and not p.upload_steps.get('create'):
                    sync_catalogue(db,job.user_id)
                    if duplicates(db,p) and not p.upload_steps.get('approval',{}).get('allow_duplicate'):
                        p.status='REVIEWED';p.message='비슷한 기존 상품이 발견되었습니다. 다시 등록 버튼을 누르고 비교 결과를 확인해주세요.';db.commit();job.status='DONE';db.commit();return
                publish_product(db,p,demo=demo)
        job.status='DONE';job.message='작업을 마쳤습니다.';db.commit()
    except Exception as exc:
        db.rollback();job=db.get(Job,job.id);job.status='FAILED'
        job.message=str(exc) if isinstance(exc,ValueError) or type(exc).__name__=='RemoteFailure' else '작업을 마치지 못했습니다. 다시 시도해주세요.'
        if job.kind in ('GENERATE','PUBLISH'):
            p=db.get(Product,job.target_id)
            if p: p.status='PARTIAL_FAILED' if p.cafe24_product_no else 'FAILED';p.message=job.message
        db.commit();logging.error('job_failed id=%s type=%s',job.id,type(exc).__name__)

def run_once():
    with SessionLocal() as db:
        job=db.scalar(select(Job).where(Job.status=='QUEUED').order_by(Job.created_at).with_for_update(skip_locked=True).limit(1))
        if not job: return False
        job.status='RUNNING';job.started_at=now();db.commit();execute(db,job);return True

def main():
    global stop
    settings.validate_runtime();guard=None
    if engine.dialect.name=='postgresql':
        guard=engine.connect()
        if not guard.execute(text('SELECT pg_try_advisory_lock(73512049)')).scalar(): raise RuntimeError('Another worker is active')
    else:
        from pathlib import Path
        Path(settings.upload_dir).mkdir(parents=True,exist_ok=True)
        guard=open(str(Path(settings.upload_dir)/'worker.lock'),'w');fcntl.flock(guard,fcntl.LOCK_EX|fcntl.LOCK_NB)
    # The exclusive worker lock proves these jobs were interrupted by a prior process.
    with SessionLocal() as db:
        for job in db.scalars(select(Job).where(Job.status=='RUNNING')):
            job.status='FAILED';job.message='작업이 중단되었습니다. 다시 시도해주세요.'
            p=db.get(Product,job.target_id) if job.kind in ('GENERATE','PUBLISH') else None
            if p: p.status='PARTIAL_FAILED' if p.cafe24_product_no else 'FAILED';p.message=job.message
        db.commit()
    def halt(*args):
        global stop
        stop=True
    signal.signal(signal.SIGTERM,halt);signal.signal(signal.SIGINT,halt)
    while not stop:
        if not run_once(): time.sleep(1)
    guard.close()
if __name__=='__main__': main()
