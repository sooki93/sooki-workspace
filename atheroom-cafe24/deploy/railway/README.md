# Railway 설치 준비

2026-09-10 기준 설치 담당자용 안내입니다. 설정 예시와 연결 호환 코드를 준비했으며, Railway 계정·서버 개설과 실제 배포는 아직 진행하지 않았습니다. 로컬 체험 데이터는 그대로 보존합니다.

## 비용과 시작 조건

Hobby는 월 최소 5달러이고, 포함 사용량을 넘으면 실제 사용량만큼 청구됩니다. 이 앱이 매월 5달러로 운영된다는 뜻은 아닙니다. OpenAI API 이용료는 별도입니다. [공식 요금](https://docs.railway.com/pricing)

운영자의 비용 승인 후 가입과 설치를 진행합니다. 처음에는 서버 사용량 한도 20달러와 그보다 낮은 알림 기준을 제안하며, 아직 승인되거나 설정된 값은 아닙니다. 한도 도달 시 작업실과 작업 처리가 중단되므로 운영 중 사용량을 보고 조정해야 합니다. 이는 세금·환율·외부 AI 비용까지 포함한 최종 결제액 보장이 아닙니다. [사용량 제한](https://docs.railway.com/pricing/cost-control)

별도 도메인 구매 없이 frontend에 제공되는 HTTPS 주소로 시작할 수 있습니다. [공개 주소 설정](https://docs.railway.com/networking/public-networking)

## 서비스 구성

하나의 프로젝트와 환경에 아래 이름으로 리소스를 생성합니다. 예시의 서비스 이름을 바꾸면 환경변수 참조도 바꿔야 합니다. 가능한 같은 지역에 배치합니다.

| 이름 | 종류 / 저장소 루트 | 실행 설정 |
|---|---|---|
| Postgres | Railway PostgreSQL, 영구 볼륨 포함 | 생성된 DATABASE_URL 사용 |
| photos | 비공개 Storage Bucket | 새 버킷의 자격정보 참조 |
| backend | GitHub, `/atheroom-cafe24/backend` | Dockerfile 기본 실행, 포트 8000, healthcheck `/health` |
| worker | GitHub, `/atheroom-cafe24/backend` | 같은 Dockerfile, 시작 명령 `python -m app.worker`, HTTP healthcheck 없음 |
| frontend | GitHub, `/atheroom-cafe24/frontend` | Dockerfile 기본 실행, 포트 3000, healthcheck `/` |

backend의 Pre-deploy Command만 `alembic upgrade head`로 설정합니다. worker에서는 마이그레이션을 실행하지 않습니다. backend와 worker는 각각 replica 1개로 시작하고 Serverless(자동 휴면)는 끕니다. 배포 교체 시 작업 중인 worker가 종료될 시간을 확보하고, 작업 실패·재시도 기록을 확인합니다.

frontend만 공개 도메인을 생성합니다. backend·worker·Postgres는 공개 주소 없이 내부망으로 연결합니다. 기존 Dockerfile은 IPv4의 모든 인터페이스에서 수신하므로 새 dual-stack 환경에서 연결을 검증합니다. 오래된 IPv6 전용 환경을 재사용할 경우 수신 주소 조정이 필요합니다. [내부망 라이브러리 설정](https://docs.railway.com/networking/private-networking/library-configuration)

위 루트 경로는 저장소 전체가 아닌 서비스별 빌드 기준입니다. [모노레포 설정](https://docs.railway.com/deployments/monorepo)

## 환경변수 입력

1. 리소스를 생성하고 frontend의 공개 도메인을 발급합니다. 아직 실제 연결 키가 없으면 전체 운영 배포를 완료할 수 없습니다.
2. [backend 환경변수 예시](backend/.env.example)를 backend와 worker 양쪽에 설정합니다. 두 서비스의 암호화 키·운영자 인증 정보·저장소와 DB 참조는 동일해야 합니다.
3. [frontend 환경변수 예시](frontend/.env.example)를 **빌드 전에** 설정합니다. `BACKEND_URL`은 Dockerfile의 ARG를 통해 Next.js 빌드에 반영되므로 주소 변경 후 다시 빌드합니다.
4. 빈 값은 실제 운영자 정보와 서비스 키로 채웁니다. 예시의 `${{...}}`는 Railway 참조 문법입니다. 로컬 `.env`나 터미널에 그대로 붙여넣는 값이 아닙니다.
5. backend 폴더에서 `python -m app.provision`으로 운영자가 정한 비밀번호의 해시와 암호화 키를 생성합니다. 실제 값은 비밀 설정과 안전한 복구 보관소에만 저장합니다. GitHub와 채팅에 올리지 않습니다.

일반 `postgresql://` 또는 `postgres://` URL은 앱에서 설치된 psycopg 3 드라이버에 맞게 변환합니다. 암호와 나머지 URL은 유지합니다.

새 Railway 버킷은 `S3_ADDRESSING_STYLE=virtual`을 사용합니다. 버킷의 `BUCKET`, `ENDPOINT`, `REGION`, `ACCESS_KEY_ID`, `SECRET_ACCESS_KEY`를 참조하며 사진은 기존 로그인 보호 경로를 통해 제공합니다. [버킷 공식 안내](https://docs.railway.com/storage-buckets)

운영 모드는 체험 로그인·SQLite·로컬 사진 저장 설정을 거부합니다. Cafe24와 OpenAI 키 누락은 별도 연결 기능 실행 시에도 확인해야 하며, 서버 healthcheck 성공만으로 연결 완료로 판단하지 않습니다.

## 카페24 연결과 검증

개발자 계정과 ‘엣더룸 상품등록 자동화’ 앱은 생성되어 있습니다. 기존 앱을 사용하고 중복 생성하지 않습니다. 앱 URL에는 실제 frontend HTTPS 주소, Redirect URI에는 같은 주소 뒤에 `/api/cafe24/callback`을 붙여 등록합니다.

앱에서 사용하는 범위는 `mall.read_product`, `mall.write_product`, `mall.read_category`입니다. 실제 권한 설정을 확인하고 운영자의 연결 승인으로 쇼핑몰을 연결합니다. 현재 앱은 Front API를 사용하지 않습니다.

배포 후 아래 순서로 확인합니다.

1. 새 운영 DB의 마이그레이션 성공 → backend 정상 → worker 시작 → frontend 로그인 및 API 연결 확인.
2. 비로그인 사진 접근 차단, 사진 업로드·미리보기·worker 작업 완료 확인. 여러 장을 한꺼번에 올릴 때 Next.js와 외부 프록시의 요청 크기 제한도 실제 최대 용량으로 확인하고 필요하면 조정.
3. 카페24 승인·최근 상품 분석·형식 확인, OpenAI 사진 분석과 설명 결과 검수.
4. 운영자가 검수한 상품 한 개를 비진열·판매 중지로 등록하고 카페24 관리자에서 이미지·상세 순서·가격·분류 확인.
5. 연결 갱신, 부분 실패 후 재시도, 서버 재시작 후 데이터·작업 보존 확인.

운영 데이터는 체험 DB와 분리합니다. DB 백업 설정과 복구를 확인하고 사진 원본도 별도로 보관합니다. 버킷 자체가 원본의 별도 백업을 대신한다고 가정하지 않습니다.

## 현재 검증 상태

백엔드 테스트 42개가 통과했고 이번 실행에서 PostgreSQL 전용 2개는 생략했습니다. 추가 검사는 DB URL 변환과 S3 주소 생성 등 외부 호출 없는 검사입니다. 실제 Railway 네트워크·저장소·배포, Cafe24 등록과 OpenAI 호출은 아직 검증하지 않았습니다. 로컬 Docker가 없어 Docker 이미지 실행 검증도 남아 있습니다.
