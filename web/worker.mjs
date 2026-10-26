import { parseLabels, parseTracking, parseHomography } from './core.mjs';

self.onmessage = async ({ data }) => {
  const { kind, file, frames, teams, publicWindow } = data;
  const progress = fraction => self.postMessage({ progress: Math.round(fraction * 100) });
  try {
    const result = kind === 'tracking' ? await parseTracking(file, frames, teams, progress)
      : kind === 'homography' ? await parseHomography(file, frames, progress)
      : await parseLabels(file, frames, progress, publicWindow);
    const buffers = Object.values(result).filter(value => ArrayBuffer.isView(value)).map(value => value.buffer);
    self.postMessage({ result }, buffers);
  } catch (error) { self.postMessage({ error: error.message }); }
};
