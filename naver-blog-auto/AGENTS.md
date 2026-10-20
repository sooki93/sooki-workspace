# 헬로뽀숑 네이버 블로그 자동 발행기

헬로뽀숑 네이버 블로그(blog.naver.com/hellopouchon)에 글을 자동으로 입력·임시저장·발행하는 로컬 대시보드입니다. Node + Playwright, 서버는 `http://localhost:4000`.

## 실행
- 처음 한 번: `npm install` (Playwright는 설치된 Google Chrome을 사용)
- 실행: `블로그 발행기 열기.command` 더블클릭, 또는 `npm start`
- 로그인: 대시보드 [네이버 로그인] → 뜨는 크롬 창에서 사용자가 직접 로그인 ("로그인 상태 유지" 체크). 프로그램은 비밀번호를 받지 않는다

## 보안 — 이 저장소는 공개 저장소
- `session/`(네이버 로그인 쿠키)은 **절대 커밋하지 않는다.** `.gitignore`에 있다
- `logs/`(에디터 캡처, 블로그 아이디), 블로그 글(`posts/*.md`), `posts/_발행기록.json`도 올리지 않는다. 저장소에는 발행기 코드만 둔다. 사진은 저장소 밖 `~/sookhee-image/`에 둔다
- 커밋 전 `git diff --cached --name-only`로 위 경로가 없는지 확인한다

## 구조
- `server.js` — 대시보드 + API, 한 번에 한 작업만 실행
- `lib/session.js` — 로그인 창, 세션 저장·만료 표시
- `lib/parse.js` — 글 파일(`posts/*.md`) → 블록
- `lib/publisher.js` — 에디터 자동 입력 (가운데 정렬 감성형 서식, 사진·캡션, 인용구, 구분선, 임시저장, 발행)
- `lib/selectors.js` — 네이버 에디터 버튼 위치. **네이버가 화면을 바꾸면 여기만 고친다.** `tools/inspect.js`로 현재 버튼 정보를 뽑을 수 있다
- `public/index.html` — 대시보드 화면
- `글쓰기_가이드.md` — 매일 글을 쓸 때의 규칙·톤·피드백
- `posts/_주제목록.md` — 주제 순서와 상태
- `skill/` — Claude 스킬 설치 파일 (`hellopouchon-blog-skill.zip`, 설치 안내 `install.md`). 스킬 원본은 `~/.claude/skills/hellopouchon-blog/`
- `config.json` — 사진 위치. `imageRoot`(글별 사진 폴더: `~/sookhee-image/헬로뽀숑이미지/블로그`), `photoLibrary`(사진 보관함: `~/sookhee-image/헬로뽀숑이미지`). 글 파일의 `images:`에는 폴더 이름만 쓴다

## 매일 글쓰기 흐름
1. `글쓰기_가이드.md` 기준으로 완성 초안 작성 → 사용자 검토
2. `posts/YYYY-MM-DD_주제.md` 작성, 사진 폴더 `~/sookhee-image/헬로뽀숑이미지/블로그/<같은 이름>/`를 만들고 **항상 Finder로 열어 사용자에게 보여준다**. 사진 보관함에 맞는 사진이 있으면 1.jpg…로 복사
3. 사용자가 검토를 끝냈다고 하면 바로 발행 (그 전에는 수정만 반영하고 다음 수정을 기다린다)

## 알려진 함정 (고친 것)
- 팝업 닫기 버튼을 `has-text("취소")`로 찾으면 툴바의 "취소선"이 눌린다 → 정확히 일치(`text-is`)만 쓴다
- 사진이 화면보다 크면 좌표 클릭이 툴바("내돈내산")에 떨어진다 → `safeClick`으로 툴바 영역 클릭을 막는다
- 캡션 칸은 사진을 선택해야 보인다 → 업로드 직후 ↑ 키로 사진 선택
- 입력 직후 저장은 거절될 수 있다 → 저장 개수가 늘었는지 확인하며 재시도
- 2단계 인증 계정은 쿠키가 먼저 생긴다 → 로그인 페이지를 벗어난 뒤 세션 저장
- 앱 내장 브라우저에서는 `confirm()`·`alert()`가 보이지 않는다 → 두 번 누르기 확인, 오류는 로그에 표시
