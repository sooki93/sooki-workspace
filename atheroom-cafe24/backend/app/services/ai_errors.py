from app.services.cafe24_service import RemoteFailure


class AIUsageLimit(RemoteFailure):
    def __init__(self):
        super().__init__('Codex 사용 한도에 도달해 작업을 보관했습니다. 한도가 회복되면 “다시 시작”을 눌러주세요. 유료 API로 전환하지 않습니다.')


class AIConnectionRequired(RemoteFailure):
    pass
