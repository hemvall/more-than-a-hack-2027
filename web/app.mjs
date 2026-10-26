import { LABELS, COLORS, segments, project, neighborFrame, errorStarts, videoDurationMatches } from './core.mjs';

const $ = id => document.getElementById(id);
const video = $('video'), canvas = $('overlay'), context = canvas.getContext('2d');
const timeline = $('timeline'), timeContext = timeline.getContext('2d');
const state = { demo: true, frame: 0, count: 1500, labels: null, parts: [], truth: null,
  truthParts: [], tracking: null, homography: null, playing: false, rate: 1, url: null,
  errors: [], generation: 0, lastListKey: '', videoCallback: null };
const cancellations = new Set();
let config;

function notice(message, error = false) {
  $('notice').textContent = message;
  $('notice').className = error ? 'error' : '';
}

function clock(frame) {
  const milliseconds = Math.round(frame * 1000 / config.fps);
  const minutes = Math.floor(milliseconds / 60000);
  const seconds = Math.floor(milliseconds / 1000) % 60;
  return `${String(minutes).padStart(2, '0')}:${String(seconds).padStart(2, '0')}.${String(milliseconds % 1000).padStart(3, '0')}`;
}

function setPlaying(playing) {
  state.playing = playing;
  $('play').textContent = playing ? 'Pause' : 'Lire';
  $('play').setAttribute('aria-label', playing ? 'Mettre en pause' : 'Lire la timeline');
}

function pause() { video.pause(); setPlaying(false); }

function realMode() {
  if (!state.demo) return;
  pause();
  Object.assign(state, { demo: false, count: config.frames, frame: 0, labels: null, parts: [],
    truth: null, truthParts: [], tracking: null, homography: null, errors: [], lastListKey: '' });
  $('mode').textContent = 'Inspection locale';
  $('sourceStatus').textContent = `Timeline tactique · ${config.fps} fps`;
}

function demo() {
  state.generation++;
  for (const cancel of [...cancellations]) cancel();
  pause();
  if (state.videoCallback !== null && video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(state.videoCallback);
  if (state.url) URL.revokeObjectURL(state.url);
  video.removeAttribute('src'); video.load(); video.hidden = true;
  const labels = new Uint8Array(1500);
  labels.fill(0, 0, 325); labels.fill(1, 325, 620); labels.fill(2, 620, 760);
  labels.fill(0, 760, 1090); labels.fill(1, 1090, 1380); labels.fill(3, 1380);
  Object.assign(state, { demo: true, frame: 0, count: 1500, labels, parts: segments(labels),
    truth: null, truthParts: [], tracking: null, homography: null, url: null, errors: [],
    lastListKey: '', videoCallback: null });
  for (const id of ['videoFile', 'predFile', 'trackFiles', 'homFile']) { $(id).value = ''; $(id).disabled = false; }
  $('publicTruth').disabled = false;
  $('videoStatus').textContent = 'MP4 · timeline originale à 25 fps';
  $('predStatus').textContent = 'CSV · frame,label · H/A/D/X';
  $('trackStatus').textContent = 'Sélectionner ATD XML + TXT ensemble';
  $('homStatus').textContent = 'CSV · projection terrain vers image';
  $('mode').textContent = 'Démo synthétique';
  $('sourceStatus').textContent = 'Données simulées · 25 fps';
  notice('La démo n’utilise aucune donnée de compétition.');
  render();
}

function refreshErrors() {
  state.errors = state.labels && state.truth ? errorStarts(state.labels, state.truth) : [];
  state.lastListKey = '';
}

function seek(frame) {
  if (!Number.isFinite(frame)) return;
  pause();
  state.frame = Math.max(0, Math.min(state.count - 1, Math.round(frame)));
  if (state.url && video.readyState >= 1) {
    // Stay inside the requested frame interval, clear of boundary rounding.
    video.currentTime = Math.max(0, Math.min(video.duration - 0.001, (state.frame + 0.1) / config.fps));
  }
  render();
}

function drawPoint(x, y, team, slot = null) {
  if (!Number.isFinite(x) || !Number.isFinite(y)) return;
  context.beginPath(); context.arc(x, y, team === 2 ? 4 : 7, 0, Math.PI * 2);
  context.fillStyle = team === 2 ? '#fff6d5' : COLORS[team]; context.fill();
  context.strokeStyle = '#111c16'; context.lineWidth = 1.5; context.stroke();
  if (slot !== null) { context.fillStyle = '#e6efe8'; context.font = '10px Consolas,monospace'; context.fillText(slot, x + 10, y + 3); }
}

function drawField() {
  const x = 110, y = 25, w = 900, h = 580;
  context.fillStyle = '#183d2b'; context.fillRect(0, 0, canvas.width, canvas.height);
  for (let i = 0; i < 10; i += 2) { context.fillStyle = '#1e4431'; context.fillRect(x + i * w / 10, y, w / 10, h); }
  context.strokeStyle = '#95b29d'; context.lineWidth = 1.4;
  context.strokeRect(x, y, w, h); context.beginPath(); context.moveTo(x + w / 2, y); context.lineTo(x + w / 2, y + h); context.stroke();
  context.beginPath(); context.arc(x + w / 2, y + h / 2, 78, 0, Math.PI * 2); context.stroke();
  for (const side of [0, 1]) {
    const left = side ? x + w - 142 : x;
    context.strokeRect(left, y + 118, 142, h - 236);
    context.strokeRect(side ? x + w - 48 : x, y + 210, 48, h - 420);
  }
  return [x, y, w, h];
}

function drawOverlay() {
  context.clearRect(0, 0, canvas.width, canvas.height);
  $('screenEmpty').hidden = state.demo || Boolean(state.url) || Boolean(state.tracking);
  $('screenMode').textContent = state.demo ? 'SIMULATION' : state.url ? 'VIDÉO LOCALE' : state.tracking ? 'TRACKING LOCAL' : 'SOURCES LOCALES';
  $('screenFrame').textContent = `F ${String(state.frame).padStart(6, '0')}`;
  if (state.demo) {
    const [x, y, w, h] = drawField();
    for (let team = 0; team < 2; team++) {
      for (let slot = 0; slot < 11; slot++) {
        const px = 0.12 + (slot % 4) * 0.18 + team * 0.15 + Math.sin(state.frame / 180 + slot) * 0.025;
        const py = 0.12 + Math.floor(slot / 4) * 0.32 + Math.cos(state.frame / 120 + slot) * 0.04;
        drawPoint(x + px * w, y + py * h, team);
      }
    }
    drawPoint(x + (0.48 + Math.sin(state.frame / 170) * 0.2) * w, y + (0.5 + Math.cos(state.frame / 90) * 0.12) * h, 2);
    $('overlayStatus').textContent = 'Positions fictives pour explorer les commandes.';
    return;
  }
  if (!state.tracking) { $('overlayStatus').textContent = 'Ajoute les fichiers ATD pour afficher les positions.'; return; }
  const { positions, teams, stride } = state.tracking;
  let transform;
  if (!state.url) {
    const [x, y, w, h] = drawField();
    transform = (px, py) => [x + px * w, y + py * h];
    $('overlayStatus').textContent = 'Vue du terrain normalisée. Les numéros sont des slots, pas des identités.';
  } else if (!state.homography || !state.homography.valid[state.frame] || !video.videoWidth) {
    $('overlayStatus').textContent = 'Superposition indisponible : homographie valide et vidéo requises.'; return;
  } else {
    const matrix = state.homography.matrices.subarray(state.frame * 9, state.frame * 9 + 9);
    const scale = Math.min(canvas.width / video.videoWidth, canvas.height / video.videoHeight);
    const left = (canvas.width - video.videoWidth * scale) / 2, top = (canvas.height - video.videoHeight * scale) / 2;
    transform = (px, py) => { const point = project(matrix, px, py); return point ? [left + point[0] * scale, top + point[1] * scale] : null; };
    $('overlayStatus').textContent = 'Tracking projeté. Vérifie les deux mi-temps ; le seeking du navigateur reste approximatif.';
  }
  for (let slot = 0; slot <= teams.length; slot++) {
    const start = state.frame * stride + slot * 2;
    const point = transform(positions[start], positions[start + 1]);
    if (point) drawPoint(...point, slot === teams.length ? 2 : teams[slot], slot === teams.length ? null : slot + 1);
  }
}

function drawTimeline() {
  timeContext.fillStyle = '#17241c'; timeContext.fillRect(0, 0, timeline.width, timeline.height);
  for (const [parts, y] of [[state.parts, 5], [state.truthParts, 38]]) {
    for (const part of parts) {
      timeContext.fillStyle = COLORS[part.label];
      timeContext.fillRect(part.start / state.count * timeline.width, y, Math.max(1, (part.end - part.start) / state.count * timeline.width), 25);
    }
  }
  const x = state.frame / Math.max(1, state.count - 1) * (timeline.width - 1);
  timeContext.strokeStyle = '#f0f5e9'; timeContext.lineWidth = 2;
  timeContext.beginPath(); timeContext.moveTo(x, 0); timeContext.lineTo(x, timeline.height); timeContext.stroke();
}

function renderList() {
  let active = 0;
  while (active + 1 < state.parts.length && state.parts[active + 1].start <= state.frame) active++;
  const key = `${active}/${state.parts.length}/${state.generation}`;
  if (key === state.lastListKey) return;
  state.lastListKey = key;
  const list = $('transitions'); list.replaceChildren();
  for (let i = Math.max(1, active - 2); i < Math.min(state.parts.length, Math.max(1, active - 2) + 5); i++) {
    const part = state.parts[i], item = document.createElement('li'), button = document.createElement('button');
    const frame = document.createElement('span'), labels = document.createElement('span');
    frame.textContent = `F ${part.start.toLocaleString('fr-FR')}`;
    labels.textContent = `${LABELS[state.parts[i - 1].label]} → ${LABELS[part.label]}`;
    button.append(frame, labels); button.addEventListener('click', () => seek(part.start));
    item.classList.toggle('active', i === active); item.append(button); list.append(item);
  }
}

function render() {
  $('frame').max = $('seek').max = state.count - 1;
  $('frame').value = $('seek').value = state.frame;
  $('seek').setAttribute('aria-valuetext', `Frame ${state.frame}, ${clock(state.frame)}`);
  $('clock').textContent = clock(state.frame);
  $('duration').textContent = `${state.count.toLocaleString('fr-FR')} frames`;
  const code = state.labels ? LABELS[state.labels[state.frame]] : 'Non chargée';
  $('prediction').textContent = code; $('prediction').className = LABELS.includes(code) ? code : '';
  $('truth').textContent = state.truth ? (state.truth[state.frame] === 3 ? 'Hors fenêtre' : LABELS[state.truth[state.frame]]) : 'Non chargée';
  const starts = state.parts.slice(1).map(part => part.start);
  for (const [id, direction] of [['prevTransition', -1], ['nextTransition', 1]]) $(id).disabled = neighborFrame(starts, state.frame, direction) === null;
  for (const [id, direction] of [['prevError', -1], ['nextError', 1]]) $(id).disabled = neighborFrame(state.errors, state.frame, direction) === null;
  const transitionCount = Math.max(0, state.parts.length - 1);
  $('transitionInfo').textContent = `${transitionCount.toLocaleString('fr-FR')} transition${transitionCount === 1 ? '' : 's'}` +
    (state.truth && state.labels ? ` · ${state.errors.length} plages d’écart sur le contrôle public` : '');
  drawOverlay(); drawTimeline(); renderList();
}

function readWithWorker(kind, file, teams, publicWindow) {
  return new Promise((resolve, reject) => {
    const worker = new Worker('/worker.mjs', { type: 'module' });
    const generation = state.generation;
    const cancel = () => { finish(); reject(new DOMException('Import annulé', 'AbortError')); };
    const finish = () => { worker.terminate(); cancellations.delete(cancel); };
    cancellations.add(cancel);
    worker.onmessage = ({ data }) => {
      if (generation !== state.generation) { cancel(); return; }
      if (data.progress !== undefined) { notice(`Lecture locale · ${data.progress} %`); return; }
      finish();
      if (data.error) reject(new Error(data.error)); else resolve(data.result);
    };
    worker.onerror = event => { event.preventDefault(); finish(); reject(new Error('Lecture impossible. Vérifie le format et les ressources disponibles.')); };
    worker.postMessage({ kind, file, frames: config.frames, teams, publicWindow });
  });
}

async function metadata(file) {
  if (file.size > 2 * 1024 * 1024) throw new Error('Métadonnées trop volumineuses.');
  const xml = new DOMParser().parseFromString(await file.text(), 'application/xml');
  if (xml.querySelector('parsererror')) throw new Error('Métadonnées XML illisibles.');
  const all = [...xml.getElementsByTagName('*')];
  const teams = all.filter(node => node.localName === 'Team').map(node => node.getAttribute('id'));
  const slots = all.filter(node => node.localName === 'Player').map(node => node.getAttribute('teamId'));
  if (teams.length !== 2 || !teams.every(Boolean) || teams[0] === teams[1] || !slots.length || slots.some(team => !teams.includes(team))) {
    throw new Error('Deux équipes et des slots rattachés à ces équipes sont requis.');
  }
  return slots.map(team => teams.indexOf(team));
}

async function importFile(input, operation) {
  if (!input.files.length) return;
  const generation = state.generation;
  input.disabled = true; notice('Lecture locale en cours…');
  try {
    const apply = await operation([...input.files]);
    if (generation !== state.generation) return;
    realMode(); apply(); refreshErrors(); render();
    notice('Source chargée. Les fichiers restent en mémoire sur cet appareil.');
  } catch (error) {
    if (generation === state.generation && error.name !== 'AbortError') notice(error.message, true);
  } finally { if (generation === state.generation) { input.disabled = false; input.value = ''; } }
}

async function setup() {
  const response = await fetch('/config.json');
  if (!response.ok) throw new Error('Configuration locale indisponible. Lance python -m viewer.');
  config = await response.json();
  $('predFile').addEventListener('change', event => importFile(event.target, async ([file]) => {
    const result = await readWithWorker('labels', file);
    return () => { state.labels = result.labels; state.parts = result.segments; $('predStatus').textContent = file.name; };
  }));
  $('trackFiles').addEventListener('change', event => importFile(event.target, async files => {
    const meta = files.filter(file => /\.xml$/i.test(file.name)), raw = files.filter(file => /\.txt$/i.test(file.name));
    if (files.length !== 2 || meta.length !== 1 || raw.length !== 1) throw new Error('Sélectionne ensemble un XML ATD et son TXT tactique.');
    const generation = state.generation, teams = await metadata(meta[0]);
    if (generation !== state.generation) throw new DOMException('Import annulé', 'AbortError');
    const tracking = await readWithWorker('tracking', raw[0], teams);
    return () => { state.tracking = tracking; $('trackStatus').textContent = `${teams.length} slots · XML + TXT chargés`; };
  }));
  $('homFile').addEventListener('change', event => importFile(event.target, async ([file]) => {
    const result = await readWithWorker('homography', file);
    return () => { state.homography = result; $('homStatus').textContent = file.name; };
  }));
  $('videoFile').addEventListener('change', event => importFile(event.target, async ([file]) => {
    const url = URL.createObjectURL(file), probe = document.createElement('video');
    probe.preload = 'metadata';
    const generation = state.generation;
    try {
      await new Promise((resolve, reject) => {
        const cancel = () => { cleanup(); probe.removeAttribute('src'); probe.load(); reject(new DOMException('Import annulé', 'AbortError')); };
        const cleanup = () => { cancellations.delete(cancel); probe.onloadedmetadata = probe.onerror = null; };
        cancellations.add(cancel);
        probe.onloadedmetadata = () => {
          cleanup();
          if (!videoDurationMatches(probe.duration, config.fps, config.frames)) reject(new Error('Durée incompatible : sélectionne la vidéo tactique complète à 25 fps.'));
          else resolve();
        };
        probe.onerror = () => { cleanup(); reject(new Error('Vidéo illisible ou codec non pris en charge.')); };
        probe.src = url;
      });
    } catch (error) { probe.removeAttribute('src'); probe.load(); URL.revokeObjectURL(url); throw error; }
    if (generation !== state.generation) { URL.revokeObjectURL(url); throw new DOMException('Import annulé', 'AbortError'); }
    if (state.demo) pause();
    return () => {
      if (generation !== state.generation) { URL.revokeObjectURL(url); return; }
      pause(); if (state.url) URL.revokeObjectURL(state.url);
      state.url = url; video.src = url; video.hidden = false; video.playbackRate = state.rate;
      $('videoStatus').textContent = file.name;
      probe.removeAttribute('src'); probe.load();
    };
  }));
  $('publicTruth').addEventListener('click', async () => {
    const generation = state.generation;
    $('publicTruth').disabled = true;
    try {
      notice('Lecture de la référence publique locale…');
      const response = await fetch('/public-ground-truth.csv');
      if (!response.ok) throw new Error('Référence publique indisponible.');
      const file = await response.blob();
      if (generation !== state.generation) return;
      const result = await readWithWorker('labels', file, undefined, config.publicWindow);
      if (generation !== state.generation) return;
      realMode(); state.truth = result.labels; state.truthParts = result.segments;
      refreshErrors(); seek(config.publicWindow[0]);
      notice('Fenêtre publique chargée : contrôle du pipeline uniquement, sans tuning.');
    } catch (error) { if (generation === state.generation && error.name !== 'AbortError') notice(error.message, true); }
    finally { if (generation === state.generation) $('publicTruth').disabled = false; }
  });
  $('reset').addEventListener('click', demo);
  $('prevFrame').addEventListener('click', () => seek(state.frame - 1));
  $('nextFrame').addEventListener('click', () => seek(state.frame + 1));
  $('seek').addEventListener('input', event => seek(Number(event.target.value)));
  $('frame').addEventListener('change', event => seek(Number(event.target.value)));
  $('speed').addEventListener('change', event => { state.rate = Number(event.target.value); video.playbackRate = state.rate; });
  timeline.addEventListener('click', event => { const rect = timeline.getBoundingClientRect(); seek((event.clientX - rect.left) / rect.width * (state.count - 1)); });
  for (const [id, direction, errors] of [['prevTransition', -1, false], ['nextTransition', 1, false], ['prevError', -1, true], ['nextError', 1, true]]) {
    $(id).addEventListener('click', () => { const frame = neighborFrame(errors ? state.errors : state.parts.slice(1).map(part => part.start), state.frame, direction); if (frame !== null) seek(frame); });
  }
  async function toggle() {
    if (state.playing) { pause(); return; }
    if (state.frame === state.count - 1) seek(0);
    if (state.url) { try { await video.play(); } catch { notice('Lecture vidéo impossible. Essaie un codec pris en charge.', true); } }
    else setPlaying(true);
  }
  $('play').addEventListener('click', toggle);
  document.addEventListener('keydown', event => {
    if (event.target.closest('input,select,button,a,textarea')) return;
    if (event.code === 'Space') { event.preventDefault(); toggle(); }
    if (event.code === 'ArrowLeft') { event.preventDefault(); seek(state.frame - 1); }
    if (event.code === 'ArrowRight') { event.preventDefault(); seek(state.frame + 1); }
  });
  function videoFrame(mediaTime) {
    state.frame = Math.max(0, Math.min(state.count - 1, Math.floor(mediaTime * config.fps + 0.0001)));
    render();
  }
  function scheduleVideo() {
    if (!video.requestVideoFrameCallback) return;
    if (state.videoCallback !== null) video.cancelVideoFrameCallback(state.videoCallback);
    state.videoCallback = video.requestVideoFrameCallback((_now, metadata) => { state.videoCallback = null; if (state.url) videoFrame(metadata.mediaTime); if (!video.paused) scheduleVideo(); });
  }
  video.addEventListener('play', () => { setPlaying(true); scheduleVideo(); });
  video.addEventListener('pause', () => setPlaying(false));
  video.addEventListener('ended', () => setPlaying(false));
  video.addEventListener('loadeddata', () => { if (state.url) { seek(state.frame); scheduleVideo(); } });
  video.addEventListener('seeked', () => { if (state.url) videoFrame(video.currentTime); });
  video.addEventListener('timeupdate', () => { if (state.url && !video.requestVideoFrameCallback) videoFrame(video.currentTime); });
  let previous = performance.now(), remainder = 0;
  function tick(now) {
    if (state.playing && !state.url) {
      remainder += Math.min(now - previous, 200) * config.fps * state.rate / 1000;
      const advance = Math.floor(remainder);
      if (advance) { remainder -= advance; state.frame = Math.min(state.count - 1, state.frame + advance); if (state.frame === state.count - 1) setPlaying(false); render(); }
    } else remainder = 0;
    previous = now; requestAnimationFrame(tick);
  }
  demo(); requestAnimationFrame(tick);
}

setup().catch(error => notice(error.message, true));
