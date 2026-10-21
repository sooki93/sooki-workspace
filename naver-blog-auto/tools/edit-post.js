// 이미 발행된 글을 고친다: 캡션으로 찾은 사진 삭제·교체, 문장 교체 → 수정 발행
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

    // 1-1) 사진 교체: 캡션으로 찾은 사진을 지우고, afterText 문장 뒤에 새 사진과 같은 캡션을 넣는다
    //   {"replaceImage":{"caption":"앞면에 새긴 이름","file":"/절대/경로.jpg","afterText":"앞 문단의 마지막 문장"}}
    if (spec.replaceImage) {
      const { caption, file, afterText } = spec.replaceImage;
      const imgs = frame.locator('.se-component.se-image');
      const before = await imgs.count();
      const idx = await imgs.evaluateAll((els, c) => els.findIndex((e) => (e.querySelector('.se-caption')?.innerText || '').includes(c)), caption);
      if (idx < 0) throw new Error(`바꿀 사진을 찾지 못했어요: ${caption}`);
      const target = imgs.nth(idx);
      const box = await w.boxInView(target.locator('img').first());
      await w.safeClick(box.x + box.width / 2, box.y + box.height - 60);
      await pause(400);
      await page.keyboard.press('Backspace');
      await pause(800);
      if ((await imgs.count()) !== before - 1) throw new Error('기존 사진 삭제가 확인되지 않았어요.');
      log('기존 사진 삭제 완료');

      // 앞 문단 끝에 커서를 두고 새 사진 업로드
      frame = await grab(); w = new Writer(page, frame, log);
      const para = frame.locator('.se-text-paragraph:visible', { hasText: afterText }).last();
      if (!(await para.count())) throw new Error(`사진을 넣을 위치 문장을 찾지 못했어요: ${afterText}`);
      await w.boxInView(para);
      await para.evaluate((p) => p.scrollIntoView({ block: 'center' }));
      await pause(600);
      const frameBox = frame === page.mainFrame() ? { x: 0, y: 0 } : await (await frame.frameElement()).boundingBox();
      const end = await para.evaluate((p) => { const r = document.createRange(); r.selectNodeContents(p); const rs = [...r.getClientRects()].filter((x) => x.width > 0); const z = rs[rs.length - 1]; return { x: z.right - 2, y: z.top + z.height / 2 }; });
      await w.assertInEditor(frameBox.y + end.y);
      await page.mouse.click(frameBox.x + end.x, frameBox.y + end.y);
      await page.keyboard.press('End');
      await pause(300);
      const [chooser] = await Promise.all([
        page.waitForEvent('filechooser', { timeout: 10000 }),
        frame.locator([].concat(S.toolbar.image).join(', ')).first().click(),
      ]);
      await chooser.setFiles(file);
      const deadline = Date.now() + 60000;
      while ((await imgs.count()) < before) {
        if (Date.now() > deadline) throw new Error('새 사진 업로드가 끝나지 않았어요.');
        await pause(500);
      }
      await pause(1000);
      const cap = imgs.nth(idx).locator('.se-caption').first();
      await page.keyboard.press('ArrowUp');
      if (!(await cap.isVisible().catch(() => false))) { await pause(800); await page.keyboard.press('ArrowUp'); }
      await cap.waitFor({ state: 'visible', timeout: 5000 });
      await cap.click();
      await page.keyboard.insertText(caption);
      await pause(500);
      const capNow = await imgs.nth(idx).locator('.se-caption').first().innerText();
      if (!capNow.includes(caption)) throw new Error('새 사진이 원래 자리에 들어가지 않았어요. 수정 발행하지 않았어요.');
      log(`사진 교체 완료 (${idx + 1}번째 사진)`);
    }

    // 1-2) 링크 카드 만들기: 주소만 글자로 남은 줄 끝에서 Enter를 눌러 카드를 만든다
    //   {"linkCard":"https://hellopouchon.com"}
    if (spec.linkCard) {
      frame = await grab(); w = new Writer(page, frame, log);
      const cards = frame.locator('.se-component.se-oglink');
      const before = await cards.count();
      const para = frame.locator('.se-text-paragraph:visible').filter({ hasText: new RegExp('^\\s*' + spec.linkCard.replace(/[.*+?^${}()|[\]\\/]/g, '\\$&') + '\\s*$') }).last();
      if (!(await para.count())) throw new Error(`주소만 있는 줄을 찾지 못했어요: ${spec.linkCard}`);
      await w.boxInView(para);
      await para.evaluate((p) => p.scrollIntoView({ block: 'center' }));
      await pause(600);
      const frameBox = frame === page.mainFrame() ? { x: 0, y: 0 } : await (await frame.frameElement()).boundingBox();
      const end = await para.evaluate((p) => { const r = document.createRange(); r.selectNodeContents(p); const rs = [...r.getClientRects()].filter((x) => x.width > 0); const z = rs[rs.length - 1]; return { x: z.right - 2, y: z.top + z.height / 2 }; });
      await w.assertInEditor(frameBox.y + end.y);
      await page.mouse.click(frameBox.x + end.x, frameBox.y + end.y);
      await page.keyboard.press('End');
      await page.keyboard.press('Shift+Home');
      await pause(300);
      // 주소를 다시 입력해야 카드가 만들어진다
      await page.keyboard.insertText(spec.linkCard);
      await pause(300);
      await page.keyboard.press('Enter');
      const deadline = Date.now() + 15000;
      while ((await cards.count()) <= before && Date.now() < deadline) await pause(500);
      if ((await cards.count()) <= before) throw new Error('링크 카드가 만들어지지 않았어요. 수정 발행하지 않았어요.');
      log(`링크 카드 추가 완료 (${before} → ${await cards.count()})`);
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
