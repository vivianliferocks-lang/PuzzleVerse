const STORAGE_KEY = 'puzzleverse.save.v1';
const COSTS = { 10: 1000, 20: 5000, 30: 10000, 50: 25000, 75: 50000, 100: 100000, 150: 200000, 250: 400000, 500: 1000000 };
const PLACEHOLDER_IMAGE = 'assets/puzzle-placeholder.svg';
const state = {
  player: { name: 'Guest Creator', avatar: '🧩', level: 1, coins: 2500, solved: 0, currentLevel: 1 },
  customPuzzles: [],
  unlockedPortal: {},
  leaderboards: {},
  activeGame: null
};

function save() { localStorage.setItem(STORAGE_KEY, JSON.stringify(state)); }
function load() {
  const raw = localStorage.getItem(STORAGE_KEY);
  if (!raw) return;
  try {
    const data = JSON.parse(raw);
    Object.assign(state.player, data.player || {});
    state.customPuzzles = data.customPuzzles || [];
    state.unlockedPortal = data.unlockedPortal || {};
    state.leaderboards = data.leaderboards || {};
  } catch (err) { console.warn('Save ignored', err); }
}
function $(id) { return document.getElementById(id); }
function fmtTime(sec) { const m = Math.floor(sec / 60).toString().padStart(2, '0'); const s = Math.floor(sec % 60).toString().padStart(2, '0'); return `${m}:${s}`; }
function clamp(n, a, b) { return Math.max(a, Math.min(b, n)); }
function shuffle(arr) { for (let i = arr.length - 1; i > 0; i--) { const j = Math.floor(Math.random() * (i + 1)); [arr[i], arr[j]] = [arr[j], arr[i]]; } return arr; }
function uid(prefix='pv') { return `${prefix}-${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 8)}`; }

function getPuzzleImage(level) {
  const candidates = [level.localImage, level.imageUrl, level.thumbnail, level.image];
  const usable = candidates.find(src => src && typeof src === 'string' && !src.includes('placeholder.svg'));
  return usable || level.image || PLACEHOLDER_IMAGE;
}

function renderChrome() {
  $('playerName').textContent = state.player.name;
  $('profileName').textContent = `${state.player.avatar} ${state.player.name}`;
  $('playerLevel').textContent = state.player.level;
  $('coinBalance').textContent = Math.floor(state.player.coins).toLocaleString('en-IN');
  $('avatarBtn').textContent = state.player.avatar;
  $('profileStats').textContent = `${state.player.solved} puzzles solved · ${state.customPuzzles.length} custom puzzles created`;
  $('activePuzzleCount').textContent = `${state.customPuzzles.length} / 10`;
}

function setScreen(id) {
  document.querySelectorAll('.screen').forEach(s => s.classList.remove('active-screen'));
  $(id).classList.add('active-screen');
  document.querySelectorAll('.tab').forEach(t => t.classList.toggle('active', t.dataset.screen === id));
  if (id === 'portalScreen') renderPortal();
  if (id === 'profileScreen') renderProfile();
}

function renderLevels() {
  const grid = $('levelGrid');
  grid.innerHTML = '';
  const generated = (window.PUZZLEVERSE_LEVELS || []).map((src, i) => ({ ...src, levelNumber: src.levelNumber || i + 1 }));
  window.ALL_LEVELS = generated;
  const visibleCount = Number(localStorage.getItem('puzzleverse.visibleLevels') || 120);
  generated.slice(0, visibleCount).forEach(level => {
    const locked = level.levelNumber > state.player.level;
    const image = getPuzzleImage(level);
    const card = document.createElement('article');
    card.className = 'level-card';
    card.innerHTML = `
      <img src="${image}" alt="${level.title}" loading="lazy" crossorigin="anonymous" onerror="this.onerror=null;this.src='${PLACEHOLDER_IMAGE}';" />
      <div class="card-body">
        <div class="card-row"><strong>Level ${level.levelNumber}</strong><span class="pill">${level.pieces} pcs</span></div>
        <h3>${level.title}</h3>
        <p>${level.theme || level.category || 'Puzzle'} · ${level.difficulty || 'Medium'}</p>
        <button class="${locked ? 'ghost-btn' : 'primary-btn'}" ${locked ? 'disabled' : ''}>${locked ? 'Locked' : 'Play'}</button>
      </div>`;
    card.querySelector('button').addEventListener('click', () => startPuzzle(level, 'adventure'));
    grid.appendChild(card);
  });
  if (visibleCount < generated.length) {
    const more = document.createElement('button');
    more.className = 'secondary-btn wide-load-more';
    more.textContent = `Load more levels (${visibleCount}/${generated.length})`;
    more.addEventListener('click', () => {
      localStorage.setItem('puzzleverse.visibleLevels', Math.min(generated.length, visibleCount + 120));
      renderLevels();
    });
    grid.appendChild(more);
  }
}

function renderEvents() {
  const list = $('eventList');
  if (!list || !window.PUZZLEVERSE_EVENTS) return;
  list.innerHTML = '';
  window.PUZZLEVERSE_EVENTS.forEach(ev => {
    const div = document.createElement('article');
    div.className = 'event-card';
    div.innerHTML = `<div class="card-body"><span class="eyebrow">${ev.theme}</span><h3>${ev.title}</h3><p>Reward: ${ev.reward}</p><p>Status: ${ev.status}</p><button class="secondary-btn">Preview Event Rules</button></div>`;
    div.querySelector('button').addEventListener('click', () => alert(`${ev.title}\n\nPrototype rules:\n• Solve event puzzles as fast as possible.\n• Fewer hints improve ranking.\n• Top 3 win large coin rewards.\n• Top 100 receive profile cosmetics.`));
    list.appendChild(div);
  });
}

function renderPortal() {
  const list = $('portalList');
  if (!list) return;
  list.innerHTML = '';
  const publicPuzzles = state.customPuzzles.filter(p => p.visibility === 'public');
  if (!publicPuzzles.length) {
    list.innerHTML = `<div class="panel"><h3>No public creator puzzles yet</h3><p class="small-muted">Create one from the Creator screen and publish it to the World Portal.</p></div>`;
    return;
  }
  publicPuzzles.forEach(p => {
    const cost = Math.max(100, Math.floor((COSTS[p.pieces] || 1000) * 0.1));
    const unlocked = state.unlockedPortal[p.id] || p.creator === state.player.name;
    const best = (state.leaderboards[p.id] || [])[0];
    const card = document.createElement('article');
    card.className = 'portal-card';
    card.innerHTML = `
      <img src="${p.image}" alt="${p.title}" />
      <div class="card-body">
        <div class="card-row"><strong>${p.pieces} pcs</strong><span class="pill">${p.difficulty}</span></div>
        <h3>${p.title}</h3>
        <p>By ${p.creator} · Unlock ${cost.toLocaleString('en-IN')} coins</p>
        <p class="small-muted">Best: ${best ? `${best.name} · ${fmtTime(best.time)}` : 'No record yet'}</p>
        <button class="primary-btn">${unlocked ? 'Play' : 'Unlock & Play'}</button>
      </div>`;
    card.querySelector('button').addEventListener('click', () => {
      if (!unlocked) {
        if (state.player.coins < cost) return alert('Not enough coins. Play Adventure Mode or buy coin packs in production.');
        state.player.coins -= cost;
        state.unlockedPortal[p.id] = true;
        alert(`Unlocked! Creator earns ${Math.floor(cost * 0.1).toLocaleString('en-IN')} coins in the production server economy.`);
        save(); renderChrome();
      }
      startPuzzle(p, 'custom-play');
    });
    list.appendChild(card);
  });
}

function renderProfile() {
  renderChrome();
  const list = $('profilePuzzles');
  if (!list) return;
  list.innerHTML = '';
  if (!state.customPuzzles.length) {
    list.innerHTML = '<p class="small-muted">No custom puzzles created yet.</p>';
    return;
  }
  state.customPuzzles.forEach(p => {
    const card = document.createElement('article');
    card.className = 'portal-card';
    card.innerHTML = `<img src="${p.image}" alt="${p.title}" /><div class="card-body"><h3>${p.title}</h3><p>${p.pieces} pieces · ${p.visibility}</p><div class="card-row"><button class="primary-btn play">Play</button><button class="ghost-btn del">Delete</button></div></div>`;
    card.querySelector('.play').onclick = () => startPuzzle(p, 'custom-owner');
    card.querySelector('.del').onclick = () => { if(confirm('Delete this custom puzzle slot?')) { state.customPuzzles = state.customPuzzles.filter(x => x.id !== p.id); save(); renderProfile(); renderChrome(); } };
    list.appendChild(card);
  });
}

async function startPuzzle(level, mode) {
  setScreen('gameScreen');
  const image = getPuzzleImage(level);
  const game = {
    id: level.id,
    levelNumber: level.levelNumber || null,
    mode,
    title: level.title,
    image,
    pieces: Number(level.pieces),
    trivia: level.trivia || [],
    hints: 10,
    extraHintCost: 10,
    placed: 0,
    startedAt: Date.now(),
    timer: null,
    asked: new Set(),
    zoom: 1,
    seed: [...String(level.id)].reduce((a,c)=>a+c.charCodeAt(0), 0) + Number(level.pieces)
  };
  state.activeGame = game;
  $('gameTitle').textContent = level.title;
  $('hintCount').textContent = game.hints;
  $('hintImage').src = image;
  await buildBoard(game);
  updateHUD();
  clearInterval(game.timer);
  game.timer = setInterval(updateHUD, 1000);
}

function buildBoard(game) {
  return new Promise((resolve) => {
    const board = $('puzzleBoard');
    const tray = $('pieceTray');
    const preview = new Image();
    preview.onload = () => {
      const maxWidth = 760;
      const targetBoardBase = Math.min(maxWidth, Math.max(280, Math.floor(window.innerWidth * 0.52)));
      const aspect = preview.naturalHeight / preview.naturalWidth;
      if (!window.PVJigsaw || !window.PVJigsaw.buildLayout) {
        board.innerHTML = '<div class="panel" style="padding:20px;color:#9b1c1c;background:#fff3f3;"><strong>Jigsaw engine did not load.</strong><br>Check that <code>src/jigsawEngine.js</code> exists and that index.html loads it before app.js.</div>';
        resolve();
        return;
      }

      const layout = window.PVJigsaw.buildLayout({
        pieceCount: game.pieces,
        puzzleId: game.id,
        imageSrc: game.image,
        maxWidth: targetBoardBase
      });
      game.layout = layout;
      board.innerHTML = '';
      tray.innerHTML = '';
      board.style.width = `${layout.boardWidth}px`;
      board.style.height = `${layout.boardHeight}px`;
      board.style.setProperty('--board-bg', `url("${game.image}")`);
      board.style.setProperty('--board-bg-size', `${layout.fullW}px ${layout.fullH}px`);
      board.style.setProperty('--board-bg-position', `${layout.pad}px ${layout.pad}px`);

      const pieces = [];
      layout.pieces.forEach(spec => {
        const ghost = document.createElement('div');
        ghost.className = 'slot jigsaw-slot';
        ghost.style.left = `${spec.snapX}px`;
        ghost.style.top = `${spec.snapY}px`;
        ghost.style.width = `${spec.outerW}px`;
        ghost.style.height = `${spec.outerH}px`;
        board.appendChild(ghost);

        const piece = document.createElement('div');
        piece.className = 'piece jigsaw-piece in-tray';
        piece.draggable = true;
        piece.dataset.index = spec.index;
        piece.dataset.x = spec.snapX;
        piece.dataset.y = spec.snapY;
        piece.style.width = `${spec.outerW}px`;
        piece.style.height = `${spec.outerH}px`;
        piece.innerHTML = spec.svg;
        piece.title = 'Jigsaw piece ' + (spec.index + 1);
        piece.addEventListener('dragstart', dragStart);
        pieces.push(piece);
      });
      shuffle(pieces).forEach(p => tray.appendChild(p));
      board.addEventListener('dragover', e => e.preventDefault());
      board.addEventListener('drop', onBoardDrop);
      tray.addEventListener('dragover', e => e.preventDefault());
      tray.addEventListener('drop', onTrayDrop);
      resolve();
    };
    preview.onerror = () => {
      alert('This image could not load.');
      resolve();
    };
    preview.src = game.image;
  });
}

let dragged = null;
function dragStart(e) { dragged = e.currentTarget; }
function onTrayDrop(e) {
  e.preventDefault();
  if (!dragged || dragged.classList.contains('locked')) return;
  dragged.className = 'piece jigsaw-piece in-tray';
  dragged.style.left = '';
  dragged.style.top = '';
  dragged.style.position = '';
  $('pieceTray').appendChild(dragged);
}
function onBoardDrop(e) {
  e.preventDefault();
  if (!dragged || dragged.classList.contains('locked')) return;
  const board = $('puzzleBoard');
  const rect = board.getBoundingClientRect();
  const game = state.activeGame;
  const scale = game.zoom || 1;
  const x = (e.clientX - rect.left) / scale - dragged.offsetWidth / 2;
  const y = (e.clientY - rect.top) / scale - dragged.offsetHeight / 2;
  dragged.className = 'piece jigsaw-piece on-board';
  board.appendChild(dragged);
  const targetX = Number(dragged.dataset.x), targetY = Number(dragged.dataset.y);
  const snapDist = Math.max(26, Math.min(dragged.offsetWidth, dragged.offsetHeight) * 0.24);
  if (Math.abs(x - targetX) < snapDist && Math.abs(y - targetY) < snapDist) {
    dragged.style.left = `${targetX}px`;
    dragged.style.top = `${targetY}px`;
    dragged.classList.add('locked');
    game.placed++;
    maybeTrivia();
    if (game.placed >= game.pieces) completePuzzle();
  } else {
    dragged.style.left = `${clamp(x, 0, board.clientWidth - dragged.offsetWidth)}px`;
    dragged.style.top = `${clamp(y, 0, board.clientHeight - dragged.offsetHeight)}px`;
  }
  updateHUD();
}

function maybeTrivia() {
  const game = state.activeGame;
  if (!game.trivia.length) return;
  const pct = game.placed / game.pieces;
  [0.25, 0.5, 0.75].forEach((gate, idx) => {
    if (pct >= gate && !game.asked.has(idx) && game.trivia[idx]) {
      game.asked.add(idx);
      showTrivia(game.trivia[idx]);
    }
  });
}

function showTrivia(t) {
  $('triviaQuestion').textContent = t.q;
  const answers = $('triviaAnswers');
  answers.innerHTML = '';
  t.a.forEach((answer, idx) => {
    const btn = document.createElement('button');
    btn.textContent = answer;
    btn.onclick = () => {
      if (idx === t.correct) { state.player.coins += 50; alert('+50 coins! Correct.'); }
      else alert('Wrong answer. Continue solving.');
      save(); renderChrome(); $('triviaDialog').close();
    };
    answers.appendChild(btn);
  });
  $('triviaDialog').showModal();
}

function updateHUD() {
  const game = state.activeGame;
  if (!game) return;
  const elapsed = (Date.now() - game.startedAt) / 1000;
  const pct = Math.round((game.placed / game.pieces) * 100);
  $('gameMeta').textContent = `${game.pieces} pieces · ${fmtTime(elapsed)} · ${pct}% complete`;
  $('hintCount').textContent = game.hints;
  $('zoomLabel').textContent = `${Math.round((game.zoom || 1) * 100)}%`;
}

function completePuzzle() {
  const game = state.activeGame;
  clearInterval(game.timer);
  const elapsed = Math.round((Date.now() - game.startedAt) / 1000);
  const base = Math.max(30, Math.floor(game.pieces * 8));
  const speedBonus = Math.max(0, Math.floor(game.pieces * 12 - elapsed));
  const reward = game.mode === 'adventure' ? base + speedBonus : Math.floor(base * 0.25);
  state.player.coins += reward;
  state.player.solved += 1;

  const currentIndex = (window.ALL_LEVELS || []).findIndex(l => l.id === game.id);
  if (game.mode === 'adventure') {
    const nextUnlock = currentIndex >= 0 ? currentIndex + 2 : state.player.level + 1;
    state.player.level = Math.max(state.player.level, Math.min((window.ALL_LEVELS || []).length || 500, nextUnlock));
  }

  if (!state.leaderboards[game.id]) state.leaderboards[game.id] = [];
  state.leaderboards[game.id].push({ name: state.player.name, time: elapsed, date: new Date().toISOString() });
  state.leaderboards[game.id].sort((a,b)=>a.time-b.time);
  state.leaderboards[game.id] = state.leaderboards[game.id].slice(0, 10);
  save(); renderChrome(); renderLevels();
  setTimeout(() => openCompletionDialog(game, elapsed, reward), 100);
}

function ensureCompletionDialog() {
  let dlg = $('completeDialog');
  if (dlg) return dlg;
  dlg = document.createElement('dialog');
  dlg.id = 'completeDialog';
  dlg.className = 'modal completion-modal';
  dlg.innerHTML = `
    <h2>🎉 Puzzle Complete!</h2>
    <p id="completeSummary"></p>
    <div id="shareActions" class="answer-grid share-grid" style="display:none; margin-bottom:12px;">
      <button id="publishWorldPortal" class="primary-btn">Publish to World Portal</button>
      <button id="shareWhatsApp" class="secondary-btn">WhatsApp</button>
      <button id="shareTwitter" class="secondary-btn">X / Twitter</button>
      <button id="shareFacebook" class="secondary-btn">Facebook</button>
      <button id="copyShareText" class="ghost-btn">Copy Share Text</button>
    </div>
    <div class="answer-grid">
      <button id="completeNext" class="primary-btn">Next Puzzle</button>
      <button id="completeReplay" class="secondary-btn">Replay</button>
      <button id="completeMenu" class="ghost-btn">Back to Menu</button>
    </div>
  `;
  document.body.appendChild(dlg);
  return dlg;
}

function buildShareText(game, elapsed) {
  return `I completed \"${game.title}\" in ${fmtTime(elapsed)} on PuzzleVerse! Can you beat my time?`;
}

function shareTo(url){ window.open(url, '_blank', 'noopener,noreferrer,width=760,height=640'); }

function openCompletionDialog(game, elapsed, reward) {
  const dlg = ensureCompletionDialog();
  $('completeSummary').textContent = `Time: ${fmtTime(elapsed)} · Reward: ${reward.toLocaleString('en-IN')} coins`;
  const nextBtn = $('completeNext');
  const replayBtn = $('completeReplay');
  const menuBtn = $('completeMenu');
  const shareBox = $('shareActions');
  const shareText = buildShareText(game, elapsed);

  shareBox.style.display = game.mode === 'adventure' ? 'none' : 'grid';
  nextBtn.style.display = game.mode === 'adventure' ? 'inline-flex' : 'none';
  nextBtn.onclick = () => {
    dlg.close();
    const currentIndex = (window.ALL_LEVELS || []).findIndex(l => l.id === game.id);
    const nextLevel = currentIndex >= 0 && window.ALL_LEVELS[currentIndex + 1] ? window.ALL_LEVELS[currentIndex + 1] : window.ALL_LEVELS[0];
    if (nextLevel) startPuzzle(nextLevel, 'adventure');
    else setScreen('adventureScreen');
  };
  replayBtn.onclick = () => {
    dlg.close();
    const current = (window.ALL_LEVELS || []).find(l => l.id === game.id) || state.customPuzzles.find(p => p.id === game.id);
    if (current) startPuzzle(current, game.mode);
    else setScreen('adventureScreen');
  };
  menuBtn.onclick = () => { dlg.close(); setScreen('adventureScreen'); };

  const pub = $('publishWorldPortal');
  if (pub) pub.onclick = () => {
    const found = state.customPuzzles.find(p => p.id === game.id);
    if (found) {
      found.visibility = 'public';
      save();
      renderPortal();
      alert('Your puzzle has been published to the World Portal.');
    }
  };
  const encoded = encodeURIComponent(shareText);
  const wa = $('shareWhatsApp'); if (wa) wa.onclick = () => shareTo(`https://wa.me/?text=${encoded}`);
  const tw = $('shareTwitter'); if (tw) tw.onclick = () => shareTo(`https://twitter.com/intent/tweet?text=${encoded}`);
  const fb = $('shareFacebook'); if (fb) fb.onclick = () => shareTo(`https://www.facebook.com/sharer/sharer.php?u=${encodeURIComponent(location.href)}&quote=${encoded}`);
  const cp = $('copyShareText'); if (cp) cp.onclick = async () => { try { await navigator.clipboard.writeText(shareText); alert('Share text copied.'); } catch { alert(shareText); } };

  dlg.showModal();
}

function handleCustomSubmit(e) {
  e.preventDefault();
  if (state.customPuzzles.length >= 10) return alert('You have used all 10 active custom puzzle slots. Delete one from Profile to create another.');
  const file = $('customImage').files[0];
  if (!file || !file.type.startsWith('image/')) return alert('Please upload a valid image.');
  if (file.size > 3.5 * 1024 * 1024) return alert('Prototype safety block: please use an image below 3.5 MB. Production should compress and moderate server-side.');
  const pieces = Number($('customPieces').value);
  const cost = COSTS[pieces] || 1000;
  if (state.player.coins < cost) return alert(`Not enough coins. Required: ${cost.toLocaleString('en-IN')}`);
  const reader = new FileReader();
  reader.onload = () => {
    state.player.coins -= cost;
    const p = {
      id: uid('custom'),
      title: $('customTitle').value.trim() || 'Untitled Puzzle',
      pieces,
      image: reader.result,
      visibility: $('customVisibility').value,
      creator: state.player.name,
      difficulty: pieces < 30 ? 'Easy' : pieces < 75 ? 'Medium' : 'Hard',
      createdAt: new Date().toISOString()
    };
    state.customPuzzles.push(p);
    save(); renderChrome(); renderProfile();
    alert('Custom puzzle generated. Starting it now.');
    startPuzzle(p, 'custom-owner');
  };
  reader.readAsDataURL(file);
}

function setupUI() {
  document.querySelectorAll('.tab').forEach(tab => tab.onclick = () => setScreen(tab.dataset.screen));
  $('startCurrentLevel').onclick = () => startPuzzle(window.ALL_LEVELS[state.player.level - 1] || window.ALL_LEVELS[0], 'adventure');
  $('backToMenu').onclick = () => { if (state.activeGame?.timer) clearInterval(state.activeGame.timer); setScreen('adventureScreen'); };
  $('hintBtn').onclick = () => {
    const g = state.activeGame;
    if (!g) return;
    if (g.hints <= 0) {
      if (state.player.coins < g.extraHintCost) return alert('Not enough coins for extra hint.');
      state.player.coins -= g.extraHintCost;
    } else g.hints--;
    save(); renderChrome(); updateHUD(); $('hintDialog').showModal();
  };
  $('closeHint').onclick = () => $('hintDialog').close();
  $('shuffleBtn').onclick = () => shuffle([...$('pieceTray').children]).forEach(p => $('pieceTray').appendChild(p));
  $('zoomIn').onclick = () => setZoom((state.activeGame?.zoom || 1) + 0.1);
  $('zoomOut').onclick = () => setZoom((state.activeGame?.zoom || 1) - 0.1);
  $('customForm').addEventListener('submit', handleCustomSubmit);
  $('avatarBtn').onclick = () => { $('nameInput').value = state.player.name; $('avatarInput').value = state.player.avatar; $('avatarDialog').showModal(); };
  $('saveAvatar').onclick = () => { state.player.name = $('nameInput').value.trim() || 'Guest Creator'; state.player.avatar = $('avatarInput').value; save(); renderChrome(); $('avatarDialog').close(); };
  $('resetSave').onclick = () => { if(confirm('Reset all local prototype data?')) { localStorage.removeItem(STORAGE_KEY); location.reload(); } };
}
function setZoom(v) {
  const g = state.activeGame; if (!g) return;
  g.zoom = clamp(v, 0.6, 1.8);
  $('puzzleBoard').style.transform = `scale(${g.zoom})`;
  $('zoomLabel').textContent = `${Math.round(g.zoom * 100)}%`;
}

load();
setupUI();
renderChrome();
renderLevels();
renderEvents();
renderPortal();
renderProfile();
