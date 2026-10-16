// 글 파일(posts/*.md) → { meta, blocks }
//
// 형식
//   ---
//   title: 제목
//   tags: 태그1, 태그2
//   images: images/폴더이름
//   ---
//   ## 소제목
//   일반 문단 (빈 줄로 구분, 한 문단 안의 줄바꿈은 그대로 유지)
//   - 목록
//   □ 체크리스트 (연속된 줄은 인용구 박스 하나로 묶임)
//   [사진 1 | 캡션]
//   ---                    구분선
//   https://...            링크 (한 줄에 주소만 있을 때)

const fs = require('fs');
const path = require('path');

const IMAGE_EXTS = ['.jpg', '.jpeg', '.png', '.gif', '.webp'];

function parseFrontMatter(text) {
  const m = text.match(/^---\n([\s\S]*?)\n---\n?/);
  if (!m) return { meta: {}, body: text };
  const meta = {};
  for (const line of m[1].split('\n')) {
    const i = line.indexOf(':');
    if (i === -1) continue;
    meta[line.slice(0, i).trim()] = line.slice(i + 1).trim();
  }
  meta.tags = (meta.tags || '')
    .split(',')
    .map((t) => t.trim().replace(/^#/, ''))
    .filter(Boolean);
  return { meta, body: text.slice(m[0].length) };
}

function parseBody(body) {
  const blocks = [];
  // 빈 줄 기준으로 덩어리를 나눈 뒤, 덩어리 안에서 줄 종류별로 다시 나눈다
  const chunks = body.replace(/\r\n/g, '\n').split(/\n\s*\n/);
  for (const chunk of chunks) {
    const lines = chunk.split('\n').map((l) => l.trimEnd()).filter((l) => l.trim());
    let para = [];
    const flushPara = () => {
      if (para.length) blocks.push({ type: 'paragraph', lines: para });
      para = [];
    };
    for (let i = 0; i < lines.length; i++) {
      const line = lines[i].trim();
      let m;
      if ((m = line.match(/^##\s+(.+)$/))) {
        flushPara();
        blocks.push({ type: 'heading', text: m[1] });
      } else if (/^-{3,}$/.test(line)) {
        flushPara();
        blocks.push({ type: 'divider' });
      } else if ((m = line.match(/^\[사진\s*(\d+)\s*(?:\|\s*(.*))?\]$/))) {
        flushPara();
        blocks.push({ type: 'image', n: Number(m[1]), caption: (m[2] || '').trim() });
      } else if (/^https?:\/\/\S+$/.test(line)) {
        flushPara();
        blocks.push({ type: 'link', url: line });
      } else if (line.startsWith('□')) {
        flushPara();
        const items = [];
        while (i < lines.length && lines[i].trim().startsWith('□')) items.push(lines[i++].trim());
        i--;
        blocks.push({ type: 'checklist', lines: items });
      } else if (line.startsWith('- ')) {
        flushPara();
        const items = [];
        while (i < lines.length && lines[i].trim().startsWith('- ')) items.push(lines[i++].trim());
        i--;
        blocks.push({ type: 'list', lines: items });
      } else {
        para.push(line);
      }
    }
    flushPara();
  }
  return blocks;
}

function findImage(dir, n) {
  if (!dir || !fs.existsSync(dir)) return null;
  for (const ext of IMAGE_EXTS) {
    for (const name of [`${n}${ext}`, `${n}${ext.toUpperCase()}`]) {
      const p = path.join(dir, name);
      if (fs.existsSync(p)) return p;
    }
  }
  return null;
}

function parsePostFile(filePath) {
  const text = fs.readFileSync(filePath, 'utf8');
  const { meta, body } = parseFrontMatter(text);
  const blocks = parseBody(body);
  const imageDir = meta.images ? path.resolve(path.dirname(filePath), meta.images) : null;
  for (const b of blocks) {
    if (b.type === 'image') b.file = findImage(imageDir, b.n);
  }
  return { meta, blocks, imageDir };
}

module.exports = { parsePostFile };
