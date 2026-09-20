# sooki-workspace 작업 안내

이 저장소에는 서로 다른 프로젝트가 있습니다. 요청에 해당하는 폴더만 변경하고 다른 프로젝트의 설정·배포·데이터는 보존하세요.

## Git 브랜치 규칙

이 저장소는 **`main` 브랜치 하나만** 사용합니다.

- 새 브랜치를 만들지 마세요. 모든 작업·커밋·푸시는 `main`에서 직접 합니다.
- 작업을 시작하기 전에 현재 브랜치를 확인하세요: `git branch --show-current`
- `main`이 아니면 먼저 `git checkout main`으로 이동한 뒤 진행하세요.
- 기능별 브랜치나 Pull Request를 만들지 마세요. 사용자가 명시적으로 요청한 경우에만 예외입니다.
- 푸시는 `git push origin main`으로 합니다.

## 엣더룸 상품 작업실

`atheroom-cafe24/` 작업을 시작하기 전에 반드시 [프로젝트 AGENTS.md](atheroom-cafe24/AGENTS.md)를 읽으세요. 사용자가 `attheroom-cafe24`, 엣더룸, 카페24 상품 자동화라고 부르는 프로젝트의 실제 폴더명은 **atheroom-cafe24**입니다. 이름을 임의로 변경하지 마세요.

프로젝트 문서에는 최신 사용자 요구사항, 현재 Mac/Vercel 운영 구조, 실행·검증·복구 방법과 확인되지 않은 사항이 있습니다. 프런트엔드 작업에는 `atheroom-cafe24/frontend/AGENTS.md`의 추가 지침도 적용됩니다. 이 안내를 다른 프로젝트의 운영 규칙으로 확대하지 마세요.

## Rhino 작업공간

`rhino/` 작업을 시작하기 전에 [프로젝트 AGENTS.md](rhino/AGENTS.md)를 읽으세요.

이 저장소의 `rhino/` 폴더에는 **해당 AGENTS.md 문서만** 둡니다. 실제 Rhino 작업 파일(`.3dm`, `.3dmbak`, 미리보기 이미지, 참고 자료)은 용량이 커서 Google Drive에 보관합니다.

- Drive 폴더: 「라이노」 — <https://drive.google.com/drive/folders/19IgVj-XM33uv-eULBVQYy0blMYtEt3vW>
- 로컬 접근 경로: `G:\내 드라이브\라이노\` (Google Drive for desktop 마운트)

모델 파일을 이 저장소에 커밋하지 마세요. `.gitignore`가 Rhino 바이너리를 제외합니다.
