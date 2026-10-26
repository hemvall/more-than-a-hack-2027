import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseLabels, parseTracking, parseHomography, project, neighborFrame, errorStarts, videoDurationMatches } from '../web/core.mjs';

const blob = text => new Blob([text]);
const header = 'frame,h00,h01,h02,h10,h11,h12,h20,h21,h22,reprojection_error,valid\n';

test('video duration guards reject clips, alternate timelines and unusable metadata', () => {
  assert.equal(videoDurationMatches(199319 / 25, 25, 199319), true);
  for (const duration of [6, 164487 / 25, NaN, Infinity, 0]) assert.equal(videoDurationMatches(duration, 25, 199319), false);
});

test('labels accept BOM, CRLF, quoted fields and retain half-open segments', async () => {
  const result = await parseLabels(blob('\ufeff"frame","label"\r\n0,H\r\n1,H\r\n2, a\r\n3,X\r\n'), 4);
  assert.deepEqual([...result.labels], [0, 0, 1, 3]);
  assert.deepEqual(result.segments, [{ start: 0, end: 2, label: 0 }, { start: 2, end: 3, label: 1 }, { start: 3, end: 4, label: 3 }]);
});

test('labels reject missing, duplicate, reordered, extra or invalid rows', async () => {
  for (const text of ['0,H\n', 'frame,label\n0,H\n', 'frame,label\n0,H\n0,A\n',
    'frame,label\n1,H\n0,A\n', 'frame,label\n0,Z\n1,A\n', 'frame,label\n0,H,extra\n1,A\n',
    'frame,label\n0,H\n1,A\n2,D\n', 'frame,label\n0,"H\n1,A\n']) {
    await assert.rejects(parseLabels(blob(text), 2));
  }
});

test('public truth rejects labels outside its authorized window', async () => {
  await assert.rejects(parseLabels(blob('frame,label\n0,H\n1,A\n2,X\n'), 3, undefined, [1,1]));
  const result = await parseLabels(blob('frame,label\n0,X\n1,A\n2,X\n'), 3, undefined, [1,1]);
  assert.deepEqual([...result.labels], [3,1,3]);
});

test('ATD uses one-based IDs directly, preserves missing balls and out-of-pitch observations', async () => {
  const result = await parseTracking(blob('1:0.1,0.2,1;1.1,0.7,2:NaN,NaN,NaN\n2:0.2,0.3,1;0.6,0.7,2:0.4,0.5,3\n'), 2, [0,1]);
  assert.equal(result.stride, 6);
  assert.ok(Number.isNaN(result.positions[4]));
  assert.ok(Math.abs(result.positions[6] - 0.2) < 1e-6);
  assert.ok(result.positions[2] > 1);
  assert.deepEqual([...result.teams], [0,1]);
});

test('ATD rejects zero-based IDs, inconsistent slots, partial NaNs and infinity', async () => {
  for (const text of ['0:0.1,0.2,1:0.2,0.3,1\n', '1:0.1,0.2,1;0.2,0.3,1:0.2,0.3,1\n',
    '1:NaN,0.2,1:0.2,0.3,1\n', '1:Infinity,0.2,1:0.2,0.3,1\n',
    '1:0x10,0.2,1:0.2,0.3,1\n']) await assert.rejects(parseTracking(blob(text), 1, [0]));
});

test('homography respects valid flags and zero-based indexing', async () => {
  const result = await parseHomography(blob(header + '0,100,0,10,0,200,20,0,0,1,0.1,1\n1,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,NaN,0\n'), 2);
  assert.deepEqual([...result.valid], [1,0]);
  assert.deepEqual(project(result.matrices.subarray(0,9), 0.5, 0.5), [60,120]);
});

test('homography rejects singular matrices, negative errors and mismatched indices', async () => {
  for (const row of ['0,1,1,1,1,1,1,1,1,1,0.1,1', '0,1,0,0,0,1,0,0,0,1,-1,1',
    '1,1,0,0,0,1,0,0,0,1,0.1,1', '0,1,0,0,0,1,0,0,0,1,0.1,0']) {
    await assert.rejects(parseHomography(blob(header + row + '\n'), 1));
  }
});

test('projection drops nonfinite points and zero denominators', () => {
  assert.equal(project([1,0,0,0,1,0,0,0,0], 0.5, 0.5), null);
  assert.equal(project([1,0,0,0,1,0,0,0,1], NaN, 0.5), null);
});

test('transition navigation is strict in either direction and handles boundaries', () => {
  const starts = [10,20,30];
  assert.equal(neighborFrame(starts, 20, 1), 30);
  assert.equal(neighborFrame(starts, 20, -1), 10);
  assert.equal(neighborFrame(starts, 25, -1), 20);
  assert.equal(neighborFrame(starts, 30, 1), null);
  assert.equal(neighborFrame([], 0, -1), null);
});

test('discrepancies ignore ungraded X frames and group contiguous errors', () => {
  assert.deepEqual(errorStarts(new Uint8Array([0,1,1,1,0,0]), new Uint8Array([3,0,0,3,1,0])), [1,4]);
  assert.throws(() => errorStarts([0], [0,1]));
});
