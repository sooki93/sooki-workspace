# 헬로뽀숑 블로그 스킬 설치 안내

헬로뽀숑 네이버 블로그 글쓰기·발행·수정을 Claude가 도와주는 스킬이에요.
macOS, Windows, Linux 모두 같은 방법으로 설치해요.

## 압축 파일 구성

```
hellopouchon-blog/
├── SKILL.md              스킬 본문 (Claude가 읽는 작업 규칙)
├── install.md            이 안내서
└── scripts/
    ├── autocomplete.js   네이버 자동완성 검색어 확인
    └── verify-post.js    발행된 글 확인 (사진·소제목·캡션·체크리스트·태그)
```

이 스킬은 **블로그 자동 발행기**(`naver-blog-auto`)와 함께 써요. 발행기는 GitHub 저장소에 있어서 2단계에서 따로 받아요.
압축 파일에는 네이버 로그인 정보나 사진이 들어 있지 않아요.

---

## 준비물

| 프로그램 | 버전 | 확인 명령 |
|---|---|---|
| Claude Code (터미널 또는 Claude 데스크톱 앱) | 최신 | |
| Node.js | 18 이상 | `node --version` |
| Google Chrome | 최신 | |
| Git | 아무 버전 | `git --version` |

Node.js는 https://nodejs.org 에서 LTS 버전을 받으면 돼요.

---

## 1단계. 스킬 설치

압축을 풀고, 나온 **`hellopouchon-blog` 폴더를 통째로** Claude 스킬 폴더에 넣어요.

| OS | 스킬 폴더 |
|---|---|
| macOS / Linux | `~/.claude/skills/` |
| Windows | `C:\Users\<사용자이름>\.claude\skills\` |

**macOS / Linux (터미널)**
```bash
mkdir -p ~/.claude/skills
unzip hellopouchon-blog-skill.zip -d ~/.claude/skills/
```

**Windows (PowerShell)**
```powershell
New-Item -ItemType Directory -Force "$env:USERPROFILE\.claude\skills"
Expand-Archive hellopouchon-blog-skill.zip -DestinationPath "$env:USERPROFILE\.claude\skills"
```

설치되면 `.claude/skills/hellopouchon-blog/SKILL.md` 경로에 파일이 있어야 해요.

---

## 2단계. 블로그 자동 발행기 설치

**macOS / Linux**
```bash
git clone https://github.com/sooki93/sooki-workspace.git ~/GitHub/sooki-workspace
cd ~/GitHub/sooki-workspace/naver-blog-auto
npm install
```

**Windows (PowerShell)**
```powershell
git clone https://github.com/sooki93/sooki-workspace.git "$env:USERPROFILE\GitHub\sooki-workspace"
cd "$env:USERPROFILE\GitHub\sooki-workspace\naver-blog-auto"
npm install
```

- 발행기는 설치된 **Google Chrome**을 사용해요. Chrome이 없다면 `npx playwright install chromium`을 한 번 실행하세요.
- 다른 위치에 받았다면, `SKILL.md`의 **"위치"** 항목에 있는 `~/GitHub/sooki-workspace` 경로를 실제 위치로 바꿔주세요.

---

## 3단계. 사진 폴더 설정

발행기는 글마다 사진을 아래 폴더에서 찾아요. `naver-blog-auto/config.json`에 적혀 있어요.

```json
{
  "imageRoot": "~/sookhee-image/헬로뽀숑이미지/블로그",
  "photoLibrary": "~/sookhee-image/헬로뽀숑이미지"
}
```

- `~`는 홈 폴더예요. Windows에서도 그대로 두면 `C:\Users\<사용자이름>\sookhee-image\…`로 읽어요.
- 폴더가 없으면 만들어주세요.
  - macOS / Linux: `mkdir -p ~/sookhee-image/헬로뽀숑이미지/블로그`
  - Windows: `New-Item -ItemType Directory -Force "$env:USERPROFILE\sookhee-image\헬로뽀숑이미지\블로그"`
- 다른 위치를 쓰려면 `config.json`의 두 경로를 바꾸면 돼요.

---

## 4단계. 실행과 네이버 로그인

```bash
cd ~/GitHub/sooki-workspace/naver-blog-auto
npm start
```

1. 브라우저에서 **http://localhost:4000** 을 열어요.
   - macOS는 `블로그 발행기 열기.command`를 더블클릭해도 돼요.
2. 오른쪽 위 **[네이버 로그인]**을 눌러요.
3. 뜨는 크롬 창에서 **헬로뽀숑 블로그 아이디로 직접** 로그인해요.
   - **"로그인 상태 유지"를 꼭 체크**하세요. 체크하지 않으면 하루 만에 만료돼요.
   - 2단계 인증이 나오면 끝까지 진행하세요. 블로그 화면으로 넘어가면 창이 자동으로 닫혀요.
4. 배지가 **"로그인됨"**이 되면 끝이에요.

로그인 정보는 그 컴퓨터의 `naver-blog-auto/session/` 폴더에만 저장돼요. 이 폴더는 다른 사람과 공유하거나 GitHub에 올리지 마세요.

---

## 5단계. 동작 확인

**도우미 스크립트** (모든 OS 공통)
```bash
node ~/.claude/skills/hellopouchon-blog/scripts/autocomplete.js "돌선물"
node ~/.claude/skills/hellopouchon-blog/scripts/verify-post.js
```
Windows에서는 `~` 대신 `$env:USERPROFILE`을 써요.

첫 번째 명령은 자동완성 검색어 목록을, 두 번째 명령은 블로그 최근 글 목록을 보여주면 정상이에요.

**Claude에서**
Claude Code에 **"오늘 블로그 글 써줘"**라고 말해보세요. 스킬이 자동으로 쓰이면서 순서대로 진행돼요.
1. 검색어 확인
2. 초안 작성
3. 사진 폴더 열기
4. 발행 안내

---

## 문제 해결

| 증상 | 해결 |
|---|---|
| 대시보드가 안 열려요 | `npm start`가 실행 중인지 확인하세요. 4000번 포트를 다른 프로그램이 쓰고 있으면 `PORT=4100 npm start`로 실행하세요. Windows는 `$env:PORT=4100; npm start`예요 |
| "세션 만료 · 다시 로그인" | [네이버 로그인]을 다시 누르고 "로그인 상태 유지"를 체크하세요 |
| 크롬 창이 안 떠요 | Chrome을 설치하거나 `npx playwright install chromium`을 실행하세요 |
| 사진이 "파일 없음"으로 나와요 | 글의 사진 폴더에 `1.jpg`, `2.png`처럼 **번호 이름**으로 넣었는지 확인하세요 |
| 자동 입력이 중간에 멈춰요 | 네이버 에디터 화면이 바뀐 경우예요. `naver-blog-auto/lib/selectors.js`를 고쳐야 해요. Claude에게 "발행기가 멈췄어"라고 말해주세요 |
| 발행 후 블로그에 글이 없어요 | 대시보드 진행 로그의 "화면 안내" 문구를 Claude에게 알려주세요 |
