"""A heartbeat reports the worker, never the machine serving a cloud request."""
from datetime import timedelta
from sqlalchemy import select, func
from app.models import WorkerState, Job, now
from app.security import utc

HEARTBEAT_MAX_AGE = timedelta(seconds=45)


def record_heartbeat(db, *, online, ai_ready=False, message=''):
    state = db.get(WorkerState, 'primary')
    if state is None:
        state = WorkerState(id='primary')
        db.add(state)
    state.last_seen = now()
    state.online = online
    state.ai_ready = online and ai_ready
    state.message = message
    db.commit()


def read_status(db, user_id):
    state = db.get(WorkerState, 'primary')
    online = bool(state and state.online and now() - utc(state.last_seen) < HEARTBEAT_MAX_AGE)
    queued = db.scalar(select(func.count()).select_from(Job).where(Job.user_id == user_id, Job.status == 'QUEUED'))
    waiting = db.scalar(select(func.count()).select_from(Job).where(Job.user_id == user_id, Job.status == 'WAITING'))
    if not online:
        message = '맥북 연결 대기 중입니다. 저장된 요청은 맥북 작업 도우미가 연결되면 순서대로 처리합니다.'
    elif not state.ai_ready:
        message = state.message or '맥북은 연결됐습니다. 맥북에서 Codex 로그인을 확인해주세요.'
    else:
        message = '맥북 연결됨 · ChatGPT 구독으로 처리합니다. 유료 AI API로 전환하지 않습니다.'
    return {'online': online, 'ready': online and state.ai_ready, 'message': message,
            'queued': queued, 'waiting': waiting,
            'last_seen': utc(state.last_seen).isoformat() if state else None}
