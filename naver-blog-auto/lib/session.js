// 네이버 로그인 세션: 로그인 창 띄우기 → 쿠키 저장 → 상태 확인
//
// 비밀번호는 프로그램이 받지 않는다. 띄운 창에서 사용자가 직접 로그인하고,
// 로그인 쿠키(NID_AUT, NID_SES)가 생기면 세션 파일로 저장한다.

const fs = require('fs');
const path = require('path');
const { chromium } = require('playwright');

const SESSION_DIR = path.join(__dirname, '..', 'session');
const STATE_FILE = path.join(SESSION_DIR, 'naver-state.json');
// 발행하다가 로그인 페이지로 튕기면 만들어지는 표시 파일
const EXPIRED_FLAG = path.join(SESSION_DIR, 'expired');
const LOGIN_URL = 'https://nid.naver.com/nidlogin.login?url=https%3A%2F%2Fblog.naver.com%2F';
const LOGIN_TIMEOUT_MS = 5 * 60 * 1000;

// 설치된 크롬을 먼저 쓰고, 없으면 Playwright 기본 브라우저를 쓴다
async function launchBrowser() {
  try {
    return await chromium.launch({ channel: 'chrome', headless: false });
  } catch (e) {
    return await chromium.launch({ headless: false });
  }
}

function hasLoginCookies(cookies) {
  const names = new Set(cookies.filter((c) => c.domain.endsWith('naver.com')).map((c) => c.name));
  return names.has('NID_AUT') && names.has('NID_SES');
}

async function login(log = () => {}) {
  const browser = await launchBrowser();
  try {
    const context = await browser.newContext({ locale: 'ko-KR' });
    const page = await context.newPage();
    await page.goto(LOGIN_URL);
    log('로그인 창을 열었어요. 창에서 직접 로그인해주세요. (5분 안에) "로그인 상태 유지"를 체크하면 오래 유지돼요.');

    const deadline = Date.now() + LOGIN_TIMEOUT_MS;
    while (Date.now() < deadline) {
      if (page.isClosed()) throw new Error('로그인 창이 닫혔어요. 다시 시도해주세요.');
      // 2단계 인증·새 기기 확인이 있으면 쿠키가 먼저 생겨도 로그인이 덜 끝난 상태다.
      // 로그인 페이지(nid.naver.com)를 벗어난 뒤에 저장한다
      const done = !page.url().includes('nid.naver.com');
      if (done && hasLoginCookies(await context.cookies())) {
        // 블로그 도메인 쿠키까지 받도록 한 번 들렀다가 저장
        await page.goto('https://blog.naver.com/', { waitUntil: 'domcontentloaded' }).catch(() => {});
        fs.mkdirSync(SESSION_DIR, { recursive: true });
        await context.storageState({ path: STATE_FILE });
        fs.chmodSync(STATE_FILE, 0o600);
        if (fs.existsSync(EXPIRED_FLAG)) fs.unlinkSync(EXPIRED_FLAG);
        log('로그인 세션을 저장했어요.');
        return status();
      }
      await new Promise((r) => setTimeout(r, 1000));
    }
    throw new Error('5분 안에 로그인이 끝나지 않았어요. 다시 시도해주세요.');
  } finally {
    await browser.close().catch(() => {});
  }
}

function status() {
  if (!fs.existsSync(STATE_FILE)) return { state: 'none', label: '로그인 필요' };
  const { cookies = [] } = JSON.parse(fs.readFileSync(STATE_FILE, 'utf8'));
  const auth = cookies.filter((c) => ['NID_AUT', 'NID_SES'].includes(c.name));
  if (auth.length < 2) return { state: 'none', label: '로그인 필요' };
  // expires가 -1이면 브라우저 세션 쿠키. 실제 만료는 발행 시 로그인 페이지로 튕기는지로 판단
  const now = Date.now() / 1000;
  const expired = fs.existsSync(EXPIRED_FLAG) || auth.some((c) => c.expires !== -1 && c.expires < now);
  const savedAt = fs.statSync(STATE_FILE).mtime;
  if (expired) return { state: 'expired', label: '세션 만료 · 다시 로그인', savedAt };
  // 브라우저 세션 쿠키만 있으면 "로그인 상태 유지" 없이 로그인한 것
  const keep = auth.every((c) => c.expires !== -1);
  return { state: 'ok', label: keep ? '로그인됨' : '로그인됨 (상태 유지 안 함)', savedAt };
}

function markExpired() {
  fs.mkdirSync(SESSION_DIR, { recursive: true });
  fs.writeFileSync(EXPIRED_FLAG, new Date().toISOString());
}

function logout() {
  for (const f of [STATE_FILE, EXPIRED_FLAG]) if (fs.existsSync(f)) fs.unlinkSync(f);
  return status();
}

module.exports = { login, status, logout, markExpired, launchBrowser, STATE_FILE };
