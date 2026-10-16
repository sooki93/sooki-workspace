// 네이버 블로그 자동 발행 대시보드 서버 (http://localhost:4000)

const http = require('http');
const { execFile } = require('child_process');
const fs = require('fs');
const path = require('path');
const session = require('./lib/session');
const { parsePostFile } = require('./lib/parse');
const { publish } = require('./lib/publisher');

const PORT = Number(process.env.PORT) || 4000;
const POSTS_DIR = path.join(__dirname, 'posts');
const PUBLIC_DIR = path.join(__dirname, 'public');
const RECORD_FILE = path.join(POSTS_DIR, '_발행기록.json');

// 발행 기록: 같은 글을 두 번 올리지 않도록 대시보드에 표시
function readRecords() {
  try { return JSON.parse(fs.readFileSync(RECORD_FILE, 'utf8')); } catch { return {}; }
}
function addRecord(file, url) {
  const records = readRecords();
  records[file] = { url, at: new Date().toISOString() };
  fs.writeFileSync(RECORD_FILE, JSON.stringify(records, null, 2));
}

// 진행 로그를 대시보드로 실시간 전송 (SSE)
const clients = new Set();
const history = [];
function log(msg) {
  const line = `[${new Date().toLocaleTimeString('ko-KR')}] ${msg}`;
  history.push(line);
  if (history.length > 200) history.shift();
  console.log(line);
  for (const res of clients) res.write(`data: ${JSON.stringify(line)}\n\n`);
}

let busy = null; // 동시에 한 작업만

function send(res, code, body, type = 'application/json; charset=utf-8') {
  res.writeHead(code, { 'Content-Type': type });
  res.end(type.startsWith('application/json') ? JSON.stringify(body) : body);
}

function readJson(req) {
  return new Promise((resolve) => {
    let data = '';
    req.on('data', (c) => (data += c));
    req.on('end', () => {
      try { resolve(JSON.parse(data || '{}')); } catch { resolve({}); }
    });
  });
}

// posts 폴더 밖 파일 접근 막기
function postPath(name) {
  const p = path.resolve(POSTS_DIR, String(name || ''));
  if (!p.startsWith(POSTS_DIR + path.sep) || !p.endsWith('.md') || path.basename(p).startsWith('_') || !fs.existsSync(p)) return null;
  return p;
}

async function runJob(name, fn, res) {
  if (busy) return send(res, 409, { error: `지금 "${busy}" 작업 중이에요. 끝난 뒤 다시 눌러주세요.` });
  busy = name;
  try {
    send(res, 200, await fn());
  } catch (e) {
    log(`실패: ${e.message}`);
    send(res, 500, { error: e.message });
  } finally {
    busy = null;
  }
}

const MIME = { '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg', '.png': 'image/png', '.gif': 'image/gif', '.webp': 'image/webp' };

const server = http.createServer(async (req, res) => {
  const url = new URL(req.url, `http://localhost:${PORT}`);
  const route = `${req.method} ${url.pathname}`;

  if (route === 'GET /') return send(res, 200, fs.readFileSync(path.join(PUBLIC_DIR, 'index.html')), 'text/html; charset=utf-8');

  if (route === 'GET /api/events') {
    res.writeHead(200, { 'Content-Type': 'text/event-stream', 'Cache-Control': 'no-cache', Connection: 'keep-alive' });
    for (const line of history) res.write(`data: ${JSON.stringify(line)}\n\n`);
    clients.add(res);
    req.on('close', () => clients.delete(res));
    return;
  }

  if (route === 'GET /api/status') return send(res, 200, { ...session.status(), busy });

  if (route === 'POST /api/login') return runJob('로그인', () => session.login(log), res);

  // 선택한 글의 사진 폴더를 Finder로 연다 (없으면 만든다)
  if (route === 'POST /api/open-images') {
    const { file } = await readJson(req);
    const p = postPath(file);
    if (!p) return send(res, 404, { error: '글 파일을 찾지 못했어요.' });
    const { imageDir } = parsePostFile(p);
    if (!imageDir || !imageDir.startsWith(POSTS_DIR + path.sep)) return send(res, 400, { error: '글 파일에 images 경로가 없어요.' });
    fs.mkdirSync(imageDir, { recursive: true });
    execFile('open', [imageDir]);
    return send(res, 200, { dir: path.relative(__dirname, imageDir) });
  }

  if (route === 'POST /api/logout') {
    log('저장된 로그인 세션을 지웠어요.');
    return send(res, 200, session.logout());
  }

  if (route === 'GET /api/posts') {
    // _로 시작하는 파일(주제목록 등)은 글이 아니다. 최신 날짜 글이 위로
    const files = fs.readdirSync(POSTS_DIR).filter((f) => f.endsWith('.md') && !f.startsWith('_')).sort().reverse();
    const records = readRecords();
    return send(res, 200, files.map((f) => {
      const { meta } = parsePostFile(path.join(POSTS_DIR, f));
      return { file: f, title: meta.title || f, published: records[f] || null };
    }));
  }

  if (route === 'GET /api/post') {
    const p = postPath(url.searchParams.get('file'));
    if (!p) return send(res, 404, { error: '글 파일을 찾지 못했어요.' });
    const post = parsePostFile(p);
    post.blocks.forEach((b) => { if (b.type === 'image') b.found = Boolean(b.file); delete b.file; });
    post.imageDir = post.imageDir ? path.relative(__dirname, post.imageDir) : null;
    return send(res, 200, post);
  }

  if (route === 'GET /api/image') {
    const p = postPath(url.searchParams.get('file'));
    if (!p) return send(res, 404, { error: 'not found' });
    const img = parsePostFile(p).blocks.find((b) => b.type === 'image' && b.n === Number(url.searchParams.get('n')));
    if (!img || !img.file) return send(res, 404, { error: 'not found' });
    return send(res, 200, fs.readFileSync(img.file), MIME[path.extname(img.file).toLowerCase()] || 'application/octet-stream');
  }

  if (route === 'POST /api/publish') {
    const { file, mode } = await readJson(req);
    const p = postPath(file);
    if (!p) return send(res, 404, { error: '글 파일을 찾지 못했어요.' });
    if (!['draft', 'publish'].includes(mode)) return send(res, 400, { error: 'mode는 draft 또는 publish' });
    log(`${mode === 'publish' ? '바로 발행' : '임시저장'} 시작: ${file}`);
    return runJob(mode === 'publish' ? '발행' : '임시저장', async () => {
      const result = await publish({ file: p, mode, log });
      if (mode === 'publish' && result.ok) addRecord(file, result.url);
      return result;
    }, res);
  }

  send(res, 404, { error: 'not found' });
});

server.listen(PORT, '127.0.0.1', () => console.log(`대시보드: http://localhost:${PORT}`));
