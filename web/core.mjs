// Pure readers and timeline geometry, shared by the browser worker and Node tests.
export const LABELS = ['H', 'A', 'D', 'X'];
export const COLORS = ['#8bc5ef', '#eea69a', '#b6c3b8', '#34413b'];

export function videoDurationMatches(duration, fps, frames) {
  return Number.isFinite(duration) && duration > 0 && Math.abs(duration * fps - frames) <= 1;
}

export async function* lines(blob, maxBytes = 512 * 1024 * 1024) {
  if (blob.size > maxBytes) throw new Error('Fichier trop volumineux pour ce lecteur.');
  const reader = blob.stream().getReader();
  const decoder = new TextDecoder('utf-8', { fatal: true });
  let buffer = '';
  try {
    while (true) {
      const { value, done } = await reader.read();
      buffer += decoder.decode(value, { stream: !done });
      let newline;
      while ((newline = buffer.indexOf('\n')) !== -1) {
        yield buffer.slice(0, newline).replace(/\r$/, '');
        buffer = buffer.slice(newline + 1);
      }
      if (buffer.length > 1024 * 1024) throw new Error('Ligne trop longue.');
      if (done) break;
    }
    if (buffer.length) yield buffer.replace(/\r$/, '');
  } finally { try { await reader.cancel(); } finally { reader.releaseLock(); } }
}

export function csvRow(line) {
  const cells = [];
  let cell = '', quoted = false, closed = false;
  for (let i = 0; i < line.length; i++) {
    const char = line[i];
    if (quoted) {
      if (char === '"' && line[i + 1] === '"') { cell += '"'; i++; }
      else if (char === '"') { quoted = false; closed = true; }
      else cell += char;
    } else if (char === ',') { cells.push(cell.trim()); cell = ''; closed = false; }
    else if (char === '"' && !cell.trim() && !closed) { cell = ''; quoted = true; }
    else if (closed && char.trim()) throw new Error('CSV mal formé.');
    else cell += char;
  }
  if (quoted) throw new Error('Guillemets CSV non fermés.');
  cells.push(cell.trim());
  return cells;
}

export function segments(labels) {
  const result = [];
  for (let start = 0; start < labels.length;) {
    let end = start + 1;
    while (end < labels.length && labels[end] === labels[start]) end++;
    result.push({ start, end, label: labels[start] });
    start = end;
  }
  return result;
}

export async function parseLabels(blob, frames, progress = () => {}, publicWindow = null) {
  const labels = new Uint8Array(frames);
  let index = -1;
  for await (const line of lines(blob, 16 * 1024 * 1024)) {
    const row = csvRow(line.replace(/^\uFEFF/, ''));
    if (index === -1) {
      if (row.length !== 2 || row[0].toLowerCase() !== 'frame' || row[1].toLowerCase() !== 'label') {
        throw new Error('En-tête attendu : frame,label.');
      }
      index = 0;
      continue;
    }
    const label = LABELS.indexOf((row[1] || '').toUpperCase());
    if (row.length !== 2 || !/^\d+$/.test(row[0]) || Number(row[0]) !== index || index >= frames || label < 0) {
      throw new Error('CSV invalide : frames consécutives depuis 0 et labels H/A/D/X requis.');
    }
    if (publicWindow && (index < publicWindow[0] || index > publicWindow[1]) && label !== 3) {
      throw new Error('La référence doit être limitée à la fenêtre publique officielle.');
    }
    labels[index++] = label;
    if (!(index % 4096)) progress(index / frames);
  }
  if (index !== frames) throw new Error(`Le CSV doit contenir exactement ${frames} frames.`);
  return { labels, segments: segments(labels) };
}

function numeric(text) {
  if (/^nan$/i.test(text.trim())) return NaN;
  if (!/^[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:e[-+]?\d+)?$/i.test(text.trim()) || !Number.isFinite(Number(text))) throw new Error('Valeur numérique invalide.');
  return Number(text);
}

function point(text) {
  const values = text.split(',').map(numeric);
  if (values.length !== 3 || Number.isNaN(values[0]) !== Number.isNaN(values[1])) {
    throw new Error('Observation ATD invalide : x,y,vitesse attendus.');
  }
  return values;
}

export async function parseTracking(blob, frames, teams, progress = () => {}) {
  if (!teams.length || teams.length > 128 || teams.some(team => team !== 0 && team !== 1)) {
    throw new Error('Métadonnées des slots invalides.');
  }
  const stride = (teams.length + 1) * 2;
  const positions = new Float32Array(frames * stride);
  let index = 0;
  for await (const line of lines(blob)) {
    const fields = line.split(':');
    if (fields.length !== 3 || !/^\d+$/.test(fields[0]) || Number(fields[0]) !== index + 1 || index >= frames) {
      throw new Error('ATD invalide : IDs consécutifs depuis 1 requis.');
    }
    const players = fields[1].split(';');
    if (players.length !== teams.length) throw new Error('Le nombre de slots diffère des métadonnées.');
    const groups = [...players, fields[2]];
    for (let slot = 0; slot < groups.length; slot++) {
      const values = point(groups[slot]);
      positions[index * stride + slot * 2] = values[0];
      positions[index * stride + slot * 2 + 1] = values[1];
    }
    index++;
    if (!(index % 4096)) progress(index / frames);
  }
  if (index !== frames) throw new Error('ATD incomplet pour la vidéo tactique.');
  return { positions, teams: new Uint8Array(teams), stride, frames };
}

export async function parseHomography(blob, frames, progress = () => {}) {
  const matrices = new Float64Array(frames * 9), valid = new Uint8Array(frames);
  const columns = ['frame', ...Array.from({ length: 9 }, (_, i) => `h${Math.floor(i / 3)}${i % 3}`),
    'reprojection_error', 'valid'];
  let mapping, index = 0;
  for await (const line of lines(blob, 128 * 1024 * 1024)) {
    const row = csvRow(line.replace(/^\uFEFF/, ''));
    if (!mapping) {
      mapping = columns.map(name => row.indexOf(name));
      if (mapping.some(column => column < 0)) throw new Error('Colonnes d’homographie manquantes.');
      continue;
    }
    const values = mapping.map(column => row[column]);
    if (values.some(value => value === undefined) || !/^\d+$/.test(values[0]) || Number(values[0]) !== index || index >= frames) {
      throw new Error('Index d’homographie invalide : frames consécutives depuis 0 requises.');
    }
    const matrix = values.slice(1, 10).map(numeric);
    const error = numeric(values[10]);
    if (values[11] !== '0' && values[11] !== '1') throw new Error('Flag d’homographie invalide.');
    const flag = Number(values[11]);
    if ((flag && (matrix.some(value => !Number.isFinite(value)) || !Number.isFinite(error) || error < 0)) ||
        (!flag && matrix.some(value => !Number.isNaN(value)))) throw new Error('Homographie inutilisable ou erreur de reprojection invalide.');
    if (flag) {
      const scale = Math.max(...matrix.map(Math.abs));
      const [a,b,c,d,e,f,g,h,i] = matrix.map(value => value / scale);
      if (!scale || Math.abs(a*(e*i-f*h)-b*(d*i-f*g)+c*(d*h-e*g)) <= 1e-15) throw new Error('Matrice d’homographie singulière.');
    }
    matrices.set(matrix, index * 9);
    valid[index++] = flag;
    if (!(index % 4096)) progress(index / frames);
  }
  if (index !== frames) throw new Error('Homographie incomplète pour la vidéo tactique.');
  return { matrices, valid };
}

export function project(matrix, x, y) {
  const z = matrix[6] * x + matrix[7] * y + matrix[8];
  if (!Number.isFinite(z) || Math.abs(z) < 1e-12) return null;
  const px = (matrix[0] * x + matrix[1] * y + matrix[2]) / z;
  const py = (matrix[3] * x + matrix[4] * y + matrix[5]) / z;
  return Number.isFinite(px) && Number.isFinite(py) ? [px, py] : null;
}

export function neighborFrame(starts, frame, direction) {
  let low = 0, high = starts.length;
  while (low < high) {
    const middle = (low + high) >>> 1;
    if (starts[middle] <= frame) low = middle + 1; else high = middle;
  }
  if (direction > 0) return starts[low] ?? null;
  const index = low - 1;
  return starts[starts[index] === frame ? index - 1 : index] ?? null;
}

export function errorStarts(predictions, truth) {
  if (predictions.length !== truth.length) throw new Error('Timelines incompatibles.');
  const starts = [];
  let wasWrong = false;
  for (let i = 0; i < truth.length; i++) {
    const wrong = truth[i] !== 3 && predictions[i] !== truth[i];
    if (wrong && !wasWrong) starts.push(i);
    wasWrong = wrong;
  }
  return starts;
}
