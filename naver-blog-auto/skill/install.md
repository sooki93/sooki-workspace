# hellopouchon-blog 설치 안내

이 ZIP은 macOS, Windows, Linux의 Claude Code(터미널 또는 Claude 데스크톱 앱)에서 사용할 수 있는 개인 스킬입니다. 압축을 풀면 최상위에 `hellopouchon-blog` 폴더 하나가 있어야 하며, 그 안에 `SKILL.md`가 있어야 합니다.

헬로뽀숑 네이버 블로그(blog.naver.com/hellopouchon) 글쓰기·발행·수정을 도와주는 스킬이며, **블로그 자동 발행기**(`naver-blog-auto`)와 함께 사용합니다. 발행기는 GitHub 저장소에 있어서 따로 받습니다. ZIP에는 네이버 로그인 정보, 블로그 글, 사진이 들어 있지 않습니다.

```text
hellopouchon-blog/
├── SKILL.md              스킬 본문 (Claude가 읽는 작업 규칙)
├── install.md            이 안내서
└── scripts/
    ├── autocomplete.js   네이버 자동완성 검색어 확인
    └── verify-post.js    발행된 글 확인 (사진·소제목·캡션·체크리스트·태그)
```

## 현재 설치 파일이 저장된 폴더 열기

이 Mac에서는 설치 파일을 다음 폴더에 보관합니다.

```text
/Users/sookhee/skii
```

Finder에서 여는 방법:

1. Finder를 엽니다.
2. 키보드에서 `Command + Shift + G`를 함께 누릅니다.
3. 위 경로를 복사해 입력창에 붙여넣습니다.
4. `이동` 버튼이나 `Enter` 키를 누릅니다.

터미널에서 Finder로 바로 열려면 다음 명령을 사용합니다.

```sh
open "/Users/sookhee/skii"
```

다른 컴퓨터에서는 ZIP을 복사해 둔 폴더로 먼저 이동한 다음 아래 운영체제별 설치 방법을 따릅니다.

## 설치 전 확인

1. ZIP 안의 `SKILL.md`를 열어 내용을 검토합니다.
2. 같은 이름의 기존 스킬이 있으면 먼저 별도 위치에 백업하거나 이름을 바꿉니다.
3. 아래 프로그램이 설치되어 있는지 확인합니다.

| 프로그램 | 버전 | 확인 명령 |
|---|---|---|
| Claude Code | 최신 | |
| Node.js | 18 이상 | `node --version` |
| Google Chrome | 최신 | |
| Git | 아무 버전 | `git --version` |

Node.js는 https://nodejs.org 에서 LTS 버전을 받습니다.

## macOS

### 터미널로 설치

ZIP 파일이 있는 폴더에서 다음 명령을 실행합니다.

```sh
mkdir -p "$HOME/.claude/skills"
unzip "hellopouchon-blog-skill.zip" -d "$HOME/.claude/skills"
```

기본 설치 위치:

```text
~/.claude/skills/hellopouchon-blog/SKILL.md
```

### Finder로 설치

1. ZIP을 이중 클릭해 압축을 풉니다.
2. Finder에서 `이동` → `폴더로 이동`을 선택합니다.
3. `~/.claude/skills`를 입력합니다. 폴더가 없으면 만듭니다.
4. 압축을 푼 `hellopouchon-blog` 폴더 전체를 그곳으로 옮깁니다.

## Windows

### PowerShell로 설치

ZIP 파일이 있는 폴더에서 PowerShell을 열고 다음 명령을 실행합니다.

```powershell
$SkillsDir = Join-Path $env:USERPROFILE ".claude\skills"
New-Item -ItemType Directory -Force -Path $SkillsDir | Out-Null
Expand-Archive -LiteralPath ".\hellopouchon-blog-skill.zip" -DestinationPath $SkillsDir
```

기본 설치 위치:

```text
%USERPROFILE%\.claude\skills\hellopouchon-blog\SKILL.md
```

### 파일 탐색기로 설치

1. ZIP을 마우스 오른쪽 버튼으로 클릭하고 `모두 압축 풀기`를 선택합니다.
2. 파일 탐색기 주소창에 `%USERPROFILE%\.claude\skills`를 입력합니다. 폴더가 없으면 만듭니다.
3. 압축을 푼 `hellopouchon-blog` 폴더 전체를 그곳으로 옮깁니다.

## Linux

ZIP 파일이 있는 디렉터리에서 다음 명령을 실행합니다.

```sh
mkdir -p "$HOME/.claude/skills"
unzip "hellopouchon-blog-skill.zip" -d "$HOME/.claude/skills"
```

기본 설치 위치:

```text
~/.claude/skills/hellopouchon-blog/SKILL.md
```

그래픽 파일 관리자를 사용하는 경우 ZIP을 푼 뒤 `hellopouchon-blog` 폴더 전체를 `~/.claude/skills`로 옮기면 됩니다. 숨김 폴더가 보이지 않으면 `숨김 파일 표시`를 켭니다.

## 블로그 자동 발행기 설치

스킬과 함께 쓰는 발행기를 GitHub에서 받습니다.

macOS / Linux:

```sh
git clone https://github.com/sooki93/sooki-workspace.git "$HOME/GitHub/sooki-workspace"
cd "$HOME/GitHub/sooki-workspace/naver-blog-auto"
npm install
mkdir -p "$HOME/sookhee-image/헬로뽀숑이미지/블로그"
```

Windows (PowerShell):

```powershell
git clone https://github.com/sooki93/sooki-workspace.git "$env:USERPROFILE\GitHub\sooki-workspace"
cd "$env:USERPROFILE\GitHub\sooki-workspace\naver-blog-auto"
npm install
New-Item -ItemType Directory -Force "$env:USERPROFILE\sookhee-image\헬로뽀숑이미지\블로그" | Out-Null
```

- 발행기는 설치된 Google Chrome을 사용합니다. Chrome이 없으면 `npx playwright install chromium`을 한 번 실행합니다.
- 사진 위치는 `naver-blog-auto/config.json`의 `imageRoot`, `photoLibrary`입니다. 다른 위치를 쓰면 이 두 경로를 바꿉니다.
- 발행기를 다른 위치에 받았다면 `SKILL.md`의 "위치" 항목 경로를 실제 위치로 바꿉니다.
- 블로그 글(`posts/*.md`)은 저장소에 올리지 않으므로, 다른 컴퓨터에서는 글 파일이 비어 있는 상태로 시작합니다.

## 실행과 네이버 로그인

```sh
cd "$HOME/GitHub/sooki-workspace/naver-blog-auto"
npm start
```

1. 브라우저에서 `http://localhost:4000`을 엽니다. macOS는 `블로그 발행기 열기.command`를 이중 클릭해도 됩니다.
2. 오른쪽 위 `네이버 로그인`을 누릅니다.
3. 뜨는 크롬 창에서 헬로뽀숑 블로그 아이디로 직접 로그인합니다. `로그인 상태 유지`를 체크하고, 2단계 인증은 끝까지 진행합니다.
4. 배지가 `로그인됨`이 되면 끝입니다.

로그인 정보는 그 컴퓨터의 `naver-blog-auto/session/` 폴더에만 저장됩니다. 이 폴더는 공유하거나 GitHub에 올리지 않습니다.

## 설치 확인과 사용

설치 후 Claude Code를 다시 열고 새 대화를 시작합니다. 다음과 같이 직접 호출할 수 있습니다.

```text
/hellopouchon-blog 오늘 블로그 글 써줘
```

또는 "미아방지 목걸이로 블로그 글 써줘"처럼 자연스럽게 요청하면 Claude가 이 스킬을 선택합니다. 스킬은 초안을 먼저 보여주고 검토를 받은 뒤, 검토가 끝났다고 하면 발행합니다.

도우미 스크립트가 동작하는지 확인합니다. Windows에서는 `$HOME` 대신 `$env:USERPROFILE`을 씁니다.

```sh
node "$HOME/.claude/skills/hellopouchon-blog/scripts/autocomplete.js" "돌선물"
node "$HOME/.claude/skills/hellopouchon-blog/scripts/verify-post.js"
```

첫 번째 명령은 자동완성 검색어 목록을, 두 번째 명령은 블로그 최근 글 목록을 보여주면 정상입니다.

설치가 올바르면 다음 파일이 존재합니다.

```text
<사용자 홈>/.claude/skills/hellopouchon-blog/SKILL.md
```

## 문제 해결

| 증상 | 해결 |
|---|---|
| 대시보드가 안 열려요 | `npm start`가 실행 중인지 확인합니다. 4000번 포트가 사용 중이면 `PORT=4100 npm start`(Windows는 `$env:PORT=4100; npm start`) |
| "세션 만료 · 다시 로그인" | `네이버 로그인`을 다시 누르고 `로그인 상태 유지`를 체크합니다 |
| 크롬 창이 안 떠요 | Chrome을 설치하거나 `npx playwright install chromium`을 실행합니다 |
| 사진이 "파일 없음"으로 나와요 | 글의 사진 폴더에 `1.jpg`, `2.png`처럼 번호 이름으로 넣었는지 확인합니다 |
| 자동 입력이 중간에 멈춰요 | 네이버 에디터 화면이 바뀐 경우입니다. Claude에게 "발행기가 멈췄어"라고 말합니다 |

## 업데이트와 제거

- 업데이트: 기존 `hellopouchon-blog` 폴더를 백업한 뒤 새 ZIP의 `hellopouchon-blog` 폴더로 교체합니다. 기존 폴더 위에 무조건 덮어쓰지 마세요. 발행기는 `naver-blog-auto` 폴더에서 `git pull`로 업데이트합니다.
- 제거: Claude Code를 종료한 뒤 설치된 `hellopouchon-blog` 폴더만 휴지통으로 옮깁니다.

## 참고 문서

- [Claude Code 스킬 안내](https://docs.claude.com/en/docs/claude-code/skills)
