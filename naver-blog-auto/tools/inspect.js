// 개발용: 저장된 세션으로 글쓰기 화면을 열고 에디터 버튼 정보를 출력한다 (글은 쓰지 않음)
// 실행: node tools/inspect.js

const fs = require('fs');
const path = require('path');
const S = require('../lib/selectors');
const { launchBrowser, STATE_FILE } = require('../lib/session');

(async () => {
  const browser = await launchBrowser();
  const context = await browser.newContext({ storageState: STATE_FILE, locale: 'ko-KR', viewport: { width: 1400, height: 900 } });
  const page = await context.newPage();
  await page.goto(S.writeUrl, { waitUntil: 'domcontentloaded' });
  await page.waitForTimeout(6000);
  console.log('URL', page.url());

  const frames = page.frames().map((f) => f.url());
  console.log('FRAMES', frames);
  const target = page.frames().find((f) => /PostWriteForm|postwrite/i.test(f.url())) || page.mainFrame();
  console.log('EDITOR FRAME', target.url());

  const info = await target.evaluate(() => {
    const pick = (el) => ({
      tag: el.tagName.toLowerCase(),
      cls: el.className && el.className.toString().slice(0, 160),
      name: el.getAttribute('data-name'),
      value: el.getAttribute('data-value'),
      text: (el.innerText || el.getAttribute('aria-label') || '').trim().slice(0, 30),
      visible: !!(el.offsetWidth || el.offsetHeight),
    });
    return {
      buttons: [...document.querySelectorAll('button')].map(pick).filter((b) => b.visible),
      inputs: [...document.querySelectorAll('input')].map(pick),
      popups: [...document.querySelectorAll('[class*="popup"]')].map(pick).filter((b) => b.visible).slice(0, 20),
      title: [...document.querySelectorAll('[class*="documentTitle"], [class*="title-text"]')].map(pick).slice(0, 10),
      components: [...document.querySelectorAll('.se-component')].map(pick).slice(0, 10),
    };
  });
  const out = path.join(__dirname, '..', 'logs', 'inspect.json');
  fs.mkdirSync(path.dirname(out), { recursive: true });
  fs.writeFileSync(out, JSON.stringify({ url: page.url(), frames, info }, null, 2));
  await page.screenshot({ path: path.join(__dirname, '..', 'logs', 'inspect.png') });
  console.log('saved', out);
  await browser.close();
})().catch((e) => { console.error(e); process.exit(1); });
