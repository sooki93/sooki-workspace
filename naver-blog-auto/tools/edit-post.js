// 이미 발행된 글을 고친다: 캡션으로 찾은 사진 삭제, 문장 교체 → 수정 발행
// 실행: node tools/edit-post.js <logNo> '<JSON>'
//   JSON 예: {"removeImageCaption":"체인 길이는…","replace":[["옛 문장","새 문장"]]}
// 바꿀 대상을 찾지 못하면 발행하지 않고 멈춘다.

const S = require('../lib/selectors');
const { Writer } = require('../lib/publisher');
const { launchBrowser, STATE_FILE } = require('../lib/session');

const [logNo, specJson] = process.argv.slice(2);
const spec = JSON.parse(specJson || '{}');
const log = (m) => console.log(m);
const pause = (ms) => new Promise((r) => setTimeout(r, ms));

(async () => {
  const browser = await launchBrowser();
  const ctx = await browser.newContext({ storageState: STATE_FILE, locale: 'ko-KR', viewport: { width: 1400, height: 900 } });
  const page = await ctx.newPage();
  page.on('dialog', async (d) => { log(`네이버 확인창: "${d.message()}" → 확인`); await d.accept().catch(() => {}); });
  try {
    const blogId = 'hellopouchon';
    await page.goto(`https://blog.naver.com/PostUpdateForm.naver?blogId=${blogId}&logNo=${logNo}`, { waitUntil: 'domcontentloaded' });
    let frame = null;
    for (let i = 0; i < 40 && !frame; i++) { frame = page.frames().find((f) => /PostUpdateForm|PostWriteForm/.test(f.url()) && f !== page.mainFrame()) || null; if (!frame) await pause(500); }
    if (!frame) frame = page.mainFrame();
    await frame.locator('.se-title-text').first().waitFor({ timeout: 30000 });
    // 수정 화면은 처음에 한 번 다시 불러와지는 경우가 있어서 충분히 기다린 뒤 편집 화면을 다시 잡는다
    await pause(7000);
    const grab = async () => {
      for (let i = 0; i < 40; i++) {
        const f = page.frames().find((x) => /PostUpdateForm|PostWriteForm/.test(x.url()) && !x.isDetached());
        if (f && (await f.locator('.se-title-text').count().catch(() => 0))) return f;
        await pause(500);
      }
      return page.mainFrame();
    };
    frame = await grab();
    await frame.locator('.se-help-panel-close-button').first().click({ timeout: 2000 }).catch(() => {});
    let w = new Writer(page, frame, log);

    // 1) 캡션으로 사진 찾아 삭제
    if (spec.removeImageCaption) {
      const imgs = frame.locator('.se-component.se-image');
      const before = await imgs.count();
      const target = frame.locator('.se-component.se-image', { has: frame.locator('.se-caption', { hasText: spec.removeImageCaption }) }).first();
      if (!(await target.count())) throw new Error(`지울 사진을 찾지 못했어요: ${spec.removeImageCaption}`);
      const box = await w.boxInView(target.locator('img').first());
      await w.safeClick(box.x + box.width / 2, box.y + box.height - 60);
      await pause(400);
      await page.keyboard.press('Backspace');
      await pause(800);
      const after = await imgs.count();
      if (after !== before - 1) throw new Error(`사진 삭제가 확인되지 않았어요 (${before} → ${after})`);
      log(`사진 삭제 완료 (${before}장 → ${after}장)`);
    }

    // 2) 문장 교체: 문장을 드래그로 선택하고 새 문장을 입력
    for (const [oldText, newText] of spec.replace || []) {
      frame = await grab(); w = new Writer(page, frame, log);
      const para = frame.locator('.se-text-paragraph:visible', { hasText: oldText }).last();
      if (!(await para.count())) throw new Error(`바꿀 문장을 찾지 못했어요: ${oldText}`);
      await w.boxInView(para);
      await pause(400);
      // 수정 화면은 편집기가 iframe 없이 페이지에 바로 있다
      const frameBox = frame === page.mainFrame() ? { x: 0, y: 0 } : await (await frame.frameElement()).boundingBox();
      const r = await para.evaluate((p, phrase) => {
        const nodes = []; const walker = document.createTreeWalker(p, NodeFilter.SHOW_TEXT);
        while (walker.nextNode()) nodes.push(walker.currentNode);
        const full = nodes.map((n) => n.textContent).join('');
        const start = full.indexOf(phrase);
        const loc = (i) => { for (const n of nodes) { if (i <= n.textContent.length) return [n, i]; i -= n.textContent.length; } return null; };
        const range = document.createRange(); range.setStart(...loc(start)); range.setEnd(...loc(start + phrase.length));
        const rects = [...range.getClientRects()].filter((x) => x.width > 0);
        const a = rects[0], z = rects[rects.length - 1];
        return { x1: a.left + 1, y1: a.top + a.height / 2, x2: z.right - 1, y2: z.top + z.height / 2 };
      }, oldText);
      const x1 = frameBox.x + r.x1, y1 = frameBox.y + r.y1, x2 = frameBox.x + r.x2, y2 = frameBox.y + r.y2;
      await w.assertInEditor(y1); await w.assertInEditor(y2);
      await page.mouse.move(x1, y1); await page.mouse.down(); await page.mouse.move(x2, y2, { steps: 8 }); await page.mouse.up();
      await pause(300);
      await page.keyboard.insertText(newText);
      await pause(500);
      const ok = await frame.evaluate(([o, n]) => document.body.innerText.includes(n) && !document.body.innerText.includes(o), [oldText, newText]);
      if (!ok) throw new Error(`문장 교체가 확인되지 않았어요: ${oldText}`);
      log(`문장 교체 완료: ${newText}`);
    }

    // 3) 수정 발행 (사진 삭제가 유지됐는지 다시 확인)
    frame = await grab();
    if (spec.removeImageCaption && (await frame.locator('.se-caption', { hasText: spec.removeImageCaption }).count())) throw new Error('지운 사진이 다시 나타났어요. 수정 발행하지 않았어요.');
    await page.screenshot({ path: 'logs/edit_before_publish.png' });
    await frame.locator('button[class*="publish_btn"]').first().click();
    await pause(1500);
    await frame.locator('button[class*="confirm_btn"]').first().click();
    log('수정 발행 버튼을 눌렀어요. 반영을 확인하는 중…');
    await pause(6000);
    await browser.close();
  } catch (e) {
    await page.screenshot({ path: 'logs/edit_failed.png' }).catch(() => {});
    console.error('실패:', e.message);
    await browser.close();
    process.exit(1);
  }
})();
