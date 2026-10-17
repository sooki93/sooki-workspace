// 네이버 블로그 에디터에 글을 입력하고 임시저장 또는 발행한다
//
// 서식 (가운데 정렬 감성형)
//   - 본문 전체 가운데 정렬
//   - 문단 사이 빈 줄 한 줄, 소제목 앞뒤 빈 줄
//   - 소제목은 에디터의 "소제목" 스타일
//   - 체크리스트(□)는 인용구 박스
//   - **굵게** 표시와 목록의 "라벨:" 부분은 굵게

const fs = require('fs');
const path = require('path');
const S = require('./selectors');
const { parsePostFile } = require('./parse');
const { launchBrowser, markExpired, STATE_FILE } = require('./session');

const LOG_DIR = path.join(__dirname, '..', 'logs');
const MOD = process.platform === 'darwin' ? 'Meta' : 'Control';

let openBrowser = null; // 실패 시 창을 열어두고, 다음 실행 때 닫는다

async function first(scope, candidates, { timeout = 8000, visible = true } = {}) {
  const list = Array.isArray(candidates) ? candidates : [candidates];
  const deadline = Date.now() + timeout;
  while (Date.now() < deadline) {
    for (const sel of list) {
      const loc = scope.locator(sel);
      const n = await loc.count().catch(() => 0);
      for (let i = 0; i < n; i++) {
        const item = loc.nth(i);
        if (!visible || (await item.isVisible().catch(() => false))) return item;
      }
    }
    await new Promise((r) => setTimeout(r, 250));
  }
  throw new Error(`화면에서 찾지 못했어요: ${list.join(' | ')}`);
}

async function tryClick(scope, candidates, timeout = 1500) {
  try {
    await (await first(scope, candidates, { timeout })).click();
    return true;
  } catch {
    return false;
  }
}

const pause = (ms) => new Promise((r) => setTimeout(r, ms));

class Writer {
  constructor(page, frame, log) {
    this.page = page;
    this.frame = frame;
    this.kb = page.keyboard;
    this.log = log;
  }

  // 좌표로 누를 때 툴바·화면 밖을 누르지 않도록 막는다 (툴바에는 내돈내산 같은 버튼이 있다)
  async assertInEditor(y) {
    const toolbarBottom = await this.frame.evaluate(() => {
      const bars = [...document.querySelectorAll('[class*="toolbar"]')].filter((e) => e.offsetHeight && e.getBoundingClientRect().top < 200);
      return Math.max(0, ...bars.map((e) => e.getBoundingClientRect().bottom));
    });
    const viewH = this.page.viewportSize().height;
    if (y < toolbarBottom + 10 || y > viewH - 60) throw new Error(`누를 위치가 편집 영역 밖이에요 (y=${Math.round(y)})`);
  }

  async safeClick(x, y) {
    const toolbarBottom = await this.frame.evaluate(() => {
      // 화면 위쪽에 고정된 툴바만 (사진 위에 뜨는 작은 툴바는 제외)
      const bars = [...document.querySelectorAll('[class*="toolbar"]')].filter((e) => e.offsetHeight && e.getBoundingClientRect().top < 200);
      return Math.max(0, ...bars.map((e) => e.getBoundingClientRect().bottom));
    });
    const viewH = this.page.viewportSize().height;
    if (y < toolbarBottom + 10 || y > viewH - 60) throw new Error(`누를 위치가 편집 영역 밖이에요 (y=${Math.round(y)})`);
    await this.page.mouse.click(x, y);
  }

  // 블록 아래쪽이 편집 영역 가운데쯤 오도록 스크롤한 뒤 위치를 돌려준다
  async boxInView(locator) {
    // 에디터 본문은 페이지가 아니라 .se-content(__se-scroll-target) 상자 안에서 스크롤된다. 그 상자를 직접 움직인다
    await locator.evaluate((el) => {
      const sc = el.closest('.__se-scroll-target') || document.querySelector('.__se-scroll-target');
      if (!sc) return el.scrollIntoView({ block: 'center' });
      const r = el.getBoundingClientRect(), sr = sc.getBoundingClientRect();
      sc.scrollTop += (r.bottom - sr.top) - sc.clientHeight / 2;
    }).catch(() => {});
    await pause(300);
    const viewH = this.page.viewportSize().height;
    let box = await locator.boundingBox();
    // 스크롤은 마우스가 있는 곳에서 일어나므로, 먼저 편집 영역 한가운데로 옮긴다
    // 한 번에 크게 휠을 굴리면 무시되므로 800px씩 나눠서 굴린다
    for (let i = 0; box && i < 30; i++) {
      const bottom = box.y + box.height;
      if (bottom >= 250 && bottom <= viewH - 120) break;
      const delta = Math.max(-800, Math.min(800, bottom - viewH / 2));
      await this.page.mouse.move(650, viewH / 2);
      await this.page.mouse.wheel(0, delta);
      await pause(250);
      box = await locator.boundingBox();
    }
    return box;
  }

  // "**굵게**"는 굵게로 입력. "==강조=="는 일단 그냥 쓰고 구절을 모아뒀다가 다 쓴 뒤 applyAccents()에서 꾸민다
  // (미리 서식을 켜고 쓰거나 화살표로 위치를 세면 네이버 에디터에서 서식이 풀리거나 어긋난다)
  async typeRich(text) {
    this.accents = this.accents || [];
    for (const m of text.matchAll(/==([^=]+)==/g)) this.accents.push(m[1].replace(/\*\*/g, ''));
    const typed = text.replace(/==([^=]+)==/g, '$1');
    for (const part of typed.split(/(\*\*[^*]+\*\*)/).filter(Boolean)) {
      const bold = part.startsWith('**') && part.endsWith('**');
      if (bold) await this.kb.press(`${MOD}+b`);
      await this.kb.insertText(bold ? part.slice(2, -2) : part);
      if (bold) await this.kb.press(`${MOD}+b`);
    }
  }

  // 강조 구절을 화면에서 찾아 마우스로 드래그 선택 → 굵게 + 코랄색
  async applyAccents() {
    const frameEl = await this.frame.frameElement();
    for (const phrase of this.accents || []) {
      // 1) 구절이 있는 문단을 화면 안으로 스크롤 (페이지 안 스크롤은 에디터가 막아서 Playwright 스크롤 + 휠을 쓴다)
      const para = this.frame.locator('.se-component.se-text .se-text-paragraph:visible', { hasText: phrase }).last();
      const found = (await para.count()) > 0;
      if (found) {
        await this.boxInView(para);
        await pause(500);
      }
      // 2) 구절의 시작·끝 화면 위치
      const r = !found ? null : await para.evaluate((p, phrase) => {
        const nodes = [];
        const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) nodes.push(walker.currentNode);
        const full = nodes.map((n) => n.textContent).join('');
        const startIdx = full.indexOf(phrase);
        const locate = (idx) => {
          for (const n of nodes) { if (idx <= n.textContent.length) return [n, idx]; idx -= n.textContent.length; }
          return null;
        };
        const range = document.createRange();
        range.setStart(...locate(startIdx));
        range.setEnd(...locate(startIdx + phrase.length));
        const rects = [...range.getClientRects()].filter((x) => x.width > 0);
        const a = rects[0], z = rects[rects.length - 1];
        return { x1: a.left + 1, y1: a.top + a.height / 2, x2: z.right - 1, y2: z.top + z.height / 2 };
      }, phrase);
      // 바깥 페이지가 스크롤되면 iframe 위치도 바뀌므로 매번 다시 잰다
      const frameBox = await frameEl.boundingBox();
      if (!r) { this.log(`강조할 구절을 찾지 못했어요: ${phrase.slice(0, 20)}`); continue; }
      await pause(300);
      const x1 = frameBox.x + r.x1, y1 = frameBox.y + r.y1, x2 = frameBox.x + r.x2, y2 = frameBox.y + r.y2;
      // 클릭 후 드래그하면 더블클릭(단어 선택)이 되므로, 위치만 확인하고 바로 누른 채 끌어간다
      await this.assertInEditor(y1);
      await this.assertInEditor(y2);
      await this.page.mouse.move(x1, y1);
      await this.page.mouse.down();
      await this.page.mouse.move(x2, y2, { steps: 8 });
      await this.page.mouse.up();
      await pause(200);
      await (await first(this.frame, S.toolbar.bold)).click();
      await this.setColor(S.accentColor);
      await pause(300);
      const ok = await this.frame.evaluate(({ phrase, rgb }) => {
        const spans = [...document.querySelectorAll('.se-component.se-text .se-text-paragraph span')]
          .filter((sp) => (sp.getAttribute('style') || '').includes(rgb));
        return spans.map((sp) => sp.textContent).join('').includes(phrase);
      }, { phrase, rgb: '255, 95, 69' });
      if (!ok) this.log(`강조가 제대로 안 들어갔을 수 있어요: "${phrase.slice(0, 20)}" — 발행 전에 확인해주세요`);
    }
    if ((this.accents || []).length) this.log(`강조 ${this.accents.length}곳에 코랄색을 넣었어요.`);
  }

  async setColor(color) {
    await (await first(this.frame, S.toolbar.fontColor)).click();
    await (await first(this.frame, `button.se-color-palette[data-color="${color}"]`)).click();
    await pause(150);
  }

  async enter(n = 1) {
    for (let i = 0; i < n; i++) await this.kb.press('Enter');
  }

  async setFormat(kind) {
    await (await first(this.frame, S.toolbar.textFormat)).click();
    await (await first(this.frame, kind === 'heading' ? S.toolbar.textFormatHeading : S.toolbar.textFormatBody)).click();
    await pause(150);
  }

  async alignCenter() {
    // 에디터가 다시 그려지는 중이면 버튼이 사라질 수 있어 한 번 더 시도한다
    for (let attempt = 0; attempt < 2; attempt++) {
      try {
        await (await first(this.frame, S.toolbar.align)).click({ timeout: 5000 });
        await (await first(this.frame, S.toolbar.alignCenter)).click({ timeout: 5000 });
        await pause(150);
        return;
      } catch (e) {
        if (attempt) throw e;
        await this.kb.press('Escape').catch(() => {});
        await pause(1000);
      }
    }
  }

  async paragraph(b) {
    for (let i = 0; i < b.lines.length; i++) {
      await this.typeRich(b.lines[i]);
      if (i < b.lines.length - 1) await this.kb.press('Shift+Enter');
    }
    await this.enter(2);
  }

  async heading(b) {
    await this.enter(1);
    await this.setFormat('heading');
    await this.kb.insertText(b.text);
    await this.enter(1);
    await this.setFormat('body');
    await this.alignCenter();
    await this.enter(1);
  }

  async list(b) {
    for (const raw of b.lines) {
      const line = raw.replace(/^-\s+/, '');
      const m = line.match(/^([^:]{1,20}):\s*(.*)$/);
      await this.typeRich(m ? `· **${m[1]}** : ${m[2]}` : `· ${line}`);
      await this.enter(1);
    }
    await this.enter(1);
  }

  async checklist(b) {
    await (await first(this.frame, S.toolbar.quotation)).click();
    await pause(400);
    for (let i = 0; i < b.lines.length; i++) {
      await this.kb.insertText(b.lines[i]);
      if (i < b.lines.length - 1) await this.kb.press('Shift+Enter');
    }
    await this.exitComponent();
  }

  async divider() {
    await (await first(this.frame, S.toolbar.divider)).click();
    await pause(400);
    await this.exitComponent();
  }

  async image(b) {
    if (!b.file) {
      this.log(`사진 ${b.n}: 파일이 없어서 건너뛰었어요.`);
      return;
    }
    const before = await this.frame.locator(S.imageComponent).count();
    const [chooser] = await Promise.all([
      this.page.waitForEvent('filechooser', { timeout: 10000 }),
      (await first(this.frame, S.toolbar.image)).click(),
    ]);
    await chooser.setFiles(b.file);
    // 업로드가 끝나 사진이 하나 늘어날 때까지 기다린다
    const deadline = Date.now() + 60000;
    while ((await this.frame.locator(S.imageComponent).count()) <= before) {
      if (Date.now() > deadline) throw new Error(`사진 ${b.n} 업로드가 끝나지 않았어요.`);
      await pause(500);
    }
    await pause(800);
    if (b.caption) {
      // 캡션 칸은 사진을 선택해야 나타난다
      const img = this.frame.locator(S.imageComponent).nth(before);
      const cap = img.locator(S.imageCaption).first();
      try {
        // 업로드 직후 커서는 사진 아래 줄에 있다. ↑ 키로 사진을 선택하면 캡션 칸이 나타난다
        await this.kb.press('ArrowUp');
        if (!(await cap.isVisible().catch(() => false))) {
          await pause(800);
          if (!(await cap.isVisible().catch(() => false))) await this.kb.press('ArrowUp');
        }
        await cap.waitFor({ state: 'visible', timeout: 5000 });
        await cap.click();
        await this.kb.insertText(b.caption);
      } catch {
        this.log(`사진 ${b.n}: 캡션 칸이 안 보여서 캡션은 건너뛰었어요.`);
      }
    }
    await this.exitComponent();
    this.log(`사진 ${b.n} 업로드 완료`);
  }

  async link(b) {
    await this.kb.insertText(b.url);
    await this.enter(2);
  }

  // 커서가 마지막 일반 문단에 있는지
  async caretAtEnd() {
    return this.frame.evaluate(() => {
      const comps = document.querySelectorAll('.se-component:not(.se-documentTitle)');
      const last = comps[comps.length - 1];
      const caret = document.querySelector('.se-component:not(.se-documentTitle) .se-is-focused');
      return { lastIsText: !!last && last.classList.contains('se-text'), focused: !!caret && last.contains(caret) };
    });
  }

  // 인용구·사진·구분선 같은 블록 다음 줄의 일반 문단으로 커서를 옮긴다
  async exitComponent() {
    await pause(300);
    const { lastIsText } = await this.caretAtEnd();
    const last = this.frame.locator(S.bodyComponent).last();
    const box = await this.boxInView(last);
    if (box) {
      // 블록이 선택되면 위에 투명한 선택 레이어가 덮여서, 좌표로 직접 누른다
      const y = lastIsText ? box.y + box.height / 2 : box.y + box.height + 30;
      await this.safeClick(box.x + box.width / 2, y);
      await pause(300);
      await this.kb.press('End');
    }
    await this.alignCenter().catch(() => {});
  }
}

// 에디터 확인창(se-popup) 처리. 이어쓰기·불러오기 팝업은 "취소"로 새 글을 쓰고, 그 밖의 팝업은 내용을 남기고 취소한다
async function handleEditorPopup(frame, log) {
  const popup = frame.locator('.se-popup-alert:visible, .se-popup-alert-confirm:visible').first();
  if (!(await popup.count())) return false;
  const text = ((await popup.innerText().catch(() => '')) || '').replace(/\s+/g, ' ').trim();
  const cancel = popup.locator('.se-popup-button-cancel, button:text-is("취소")').first();
  const confirm = popup.locator('.se-popup-button-confirm, button:text-is("확인")').first();
  if (await cancel.count()) {
    await cancel.click();
    log(`에디터 확인창을 취소했어요: "${text.slice(0, 60)}"`);
    // 이어쓰기를 취소하면 에디터가 새 글로 다시 그려진다. 다 그려질 때까지 기다린다
    if (text.includes('작성 중') || text.includes('이어서')) {
      await pause(3000);
      await frame.locator('.se-title-text').first().waitFor({ timeout: 15000 }).catch(() => {});
      await tryClick(frame, S.helpPanelClose);
    }
  } else if (await confirm.count()) {
    await confirm.click();
    log(`에디터 알림을 닫았어요: "${text.slice(0, 60)}"`);
  }
  await pause(500);
  return true;
}

// 자동 저장으로 불러온 이전 글이 있으면 비운다
async function clearEditor(page, frame, log) {
  const hasContent = await frame.evaluate(() => {
    const title = document.querySelector('.se-title-text');
    const comps = document.querySelectorAll('.se-component:not(.se-documentTitle)');
    const text = [...comps].map((c) => c.innerText).join('').replace('글감과 함께 나의 일상을 기록해보세요!', '').trim();
    return Boolean((title && title.innerText.trim()) || comps.length > 1 || text);
  });
  if (!hasContent) return;
  log('이전에 쓰던 글이 불러와져서 비웠어요.');
  for (const sel of [S.bodyFirstParagraph[0], '.se-title-text']) {
    await frame.locator(sel).first().click({ force: true });
    for (let i = 0; i < 2; i++) {
      await page.keyboard.press(`${MOD}+a`);
      await page.keyboard.press('Backspace');
    }
  }
}

// 블로그 공개 글 목록에서 제목으로 방금 글을 찾는다
async function waitForPublished(page, title) {
  const blogId = (page.url().match(/blog\.naver\.com\/([A-Za-z0-9_-]+)/) || [])[1];
  const norm = (t) => t.replace(/\s+/g, ' ').trim();
  const deadline = Date.now() + 60000;
  while (Date.now() < deadline) {
    await pause(3000);
    for (const f of [page, ...page.frames()]) {
      const u = f.url();
      const m = u.match(/logNo=(\d+)/) || u.match(/blog\.naver\.com\/[A-Za-z0-9_-]+\/(\d{9,})/);
      if (m && blogId) return `https://blog.naver.com/${blogId}/${m[1]}`;
    }
    if (!blogId) continue;
    const list = await page.evaluate(async (id) => {
      const r = await fetch(`https://blog.naver.com/PostTitleListAsync.naver?blogId=${id}&currentPage=1&categoryNo=0&countPerPage=5`);
      return r.text();
    }, blogId).catch(() => '');
    const items = [...list.matchAll(/"logNo":"(\d+)","title":"([^"]*)"/g)];
    for (const [, logNo, t] of items) {
      if (norm(decodeURIComponent(t.replace(/\+/g, ' '))) === norm(title)) return `https://blog.naver.com/${blogId}/${logNo}`;
    }
  }
  return null;
}

async function publish({ file, mode, log = () => {}, onDone }) {
  if (!fs.existsSync(STATE_FILE)) throw new Error('로그인 세션이 없어요. 먼저 [네이버 로그인]을 눌러주세요.');
  const post = parsePostFile(file);
  if (!post.meta.title) throw new Error('글 파일에 title이 없어요.');

  if (openBrowser) await openBrowser.close().catch(() => {});
  const browser = await launchBrowser();
  openBrowser = browser;
  const context = await browser.newContext({ storageState: STATE_FILE, locale: 'ko-KR', viewport: { width: 1400, height: 900 } });
  const page = await context.newPage();

  try {
    log('글쓰기 화면을 여는 중…');
    await page.goto(S.writeUrl, { waitUntil: 'domcontentloaded' });
    await pause(1500);
    if (page.url().includes('nid.naver.com')) {
      markExpired();
      throw new Error('세션이 만료됐어요. [네이버 로그인]을 다시 해주세요.');
    }

    // 에디터는 iframe 안에 있다
    let frame = null;
    for (let i = 0; i < 40 && !frame; i++) {
      frame = page.frames().find((f) => S.editorFrameUrl.test(f.url()));
      if (!frame) await pause(500);
    }
    if (!frame) frame = page.mainFrame();
    await first(frame, S.title, { timeout: 20000 });
    await tryClick(frame, S.helpPanelClose);
    // "작성 중인 글" 이어쓰기 팝업은 늦게 뜰 수 있어서 몇 초 기다리며 처리한다 (이전 글과 섞이지 않게 새 글로 시작)
    for (let i = 0; i < 8; i++) {
      if (await handleEditorPopup(frame, log)) break;
      await pause(500);
    }
    await clearEditor(page, frame, log);
    await handleEditorPopup(frame, log);

    log('제목 입력');
    await (await first(frame, S.title)).click();
    await page.keyboard.insertText(post.meta.title);

    log('본문 입력 시작');
    await (await first(frame, S.bodyFirstParagraph)).click();
    const w = new Writer(page, frame, log);
    await w.alignCenter();
    for (const [i, b] of post.blocks.entries()) {
      await handleEditorPopup(frame, log);
      await w[b.type](b);
      if (b.type === 'heading') log(`소제목: ${b.text}`);
      if (i % 5 === 0) await pause(100);
    }
    await w.applyAccents();

    // 시험용: 입력만 하고 저장·발행 없이 에디터를 비운다
    if (mode === 'dry') {
      if (onDone) await onDone(page, frame);
      await clearEditor(page, frame, () => {});
      await pause(1500);
      await browser.close();
      openBrowser = null;
      return { ok: true };
    }

    if (mode === 'publish') {
      log('발행 설정 여는 중…');
      await (await first(frame, S.publishButton).catch(() => first(page, S.publishButton))).click();
      await pause(800);
      const scope = (await frame.locator(S.tagInput.join(',')).count()) ? frame : page;
      const tagInput = await first(scope, S.tagInput);
      for (const tag of post.meta.tags) {
        await tagInput.click();
        await page.keyboard.insertText(tag);
        await page.keyboard.press('Enter');
        await pause(150);
      }
      await tryClick(scope, S.publicRadio);
      log('발행 중…');
      // 발행 직후 네이버가 브라우저 확인창을 띄우면 Playwright는 기본으로 '취소'한다 → 내용을 남기고 확인
      page.on('dialog', async (d) => {
        log(`네이버 확인창: "${d.message()}" → 확인`);
        await d.accept().catch(() => {});
      });
      await (await first(scope, S.publishConfirm)).click();
      // 실제로 글 목록에 올라왔는지 확인 (최대 60초)
      const url = await waitForPublished(page, post.meta.title);
      if (!url) throw new Error('발행 버튼은 눌렀지만 블로그에 글이 올라오지 않았어요. 열린 창을 확인해주세요.');
      log(`발행 완료: ${url}`);
      await browser.close();
      openBrowser = null;
      return { ok: true, url };
    }

    log('임시저장 중…');
    // 입력 직후에는 에디터가 처리 중이라 저장이 거절될 수 있어서, 개수가 늘었는지 확인하며 다시 누른다
    const countOf = async () => Number((await frame.locator(S.saveCount).first().innerText().catch(() => '')).replace(/\D/g, '')) || 0;
    const before = await countOf();
    let saved = false;
    for (let attempt = 1; attempt <= 5 && !saved; attempt++) {
      await pause(2500);
      await (await first(frame, S.saveButton).catch(() => first(page, S.saveButton))).click();
      for (let i = 0; i < 10 && !saved; i++) {
        await pause(500);
        saved = (await countOf()) > before;
      }
      if (!saved) log(`저장이 아직 안 됐어요. 다시 눌러볼게요 (${attempt}/5)`);
    }
    if (!saved) throw new Error('임시저장이 확인되지 않았어요. 열린 창에서 [저장]을 직접 눌러주세요.');
    log('임시저장 완료. 창에서 결과를 확인해보세요. 태그는 발행할 때 넣어요.');
    if (onDone) await onDone(page, frame);
    return { ok: true, url: page.url(), keptOpen: true };
  } catch (e) {
    fs.mkdirSync(LOG_DIR, { recursive: true });
    const shot = path.join(LOG_DIR, `실패_${new Date().toISOString().replace(/[:.]/g, '-')}.png`);
    await page.screenshot({ path: shot, fullPage: false }).catch(() => {});
    log(`멈춘 화면을 저장했어요: logs/${path.basename(shot)} (창은 열어둘게요)`);
    throw e;
  }
}

module.exports = { publish, Writer, clearEditor };
