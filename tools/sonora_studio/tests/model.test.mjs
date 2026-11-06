import { test } from 'node:test';
import assert from 'node:assert/strict';
import { uid, createProject, createTrack, createClip, splitClip, trimLeft, trimRight, parsePreset, validateProject, serializePreset, History, audibleTracks, assignVariant } from '../ui/model.mjs';

function fixture() {
  const project = createProject(), track = createTrack(), asset = { id: uid(), name: 'test.wav', duration: 2, channels: 2, sampleRate: 48000 };
  project.assets.push(asset); track.clips.push(createClip(asset, 1)); assignVariant(project, track, project.soundTypes[0].layers[0]);
  return { project, track, clip: track.clips[0], asset };
}
test('split keeps source offsets and outside fades; it does not add a fade at the cut', () => {
  const { track, clip } = fixture(); clip.offset = .2; clip.duration = 1.5;
  const right = splitClip(track, clip.id, 1.6);
  assert.ok(Math.abs(clip.duration - .6) < 1e-12); assert.ok(Math.abs(right.offset - .8) < 1e-12);
  assert.ok(Math.abs(right.duration - .9) < 1e-12); assert.equal(clip.fadeOut, 0); assert.equal(right.fadeIn, 0);
  assert.notEqual(clip.id, right.id); assert.equal(splitClip(track, clip.id, 1), null);
});
test('trim cannot move beyond the underlying source; left trim preserves the right edge', () => {
  const { clip } = fixture(); trimLeft(clip, 1.5, 2);
  assert.equal(clip.start, 1.5); assert.equal(clip.offset, .5); assert.equal(clip.duration, 1.5);
  trimLeft(clip, 0, 2); assert.equal(clip.start, 1); assert.equal(clip.offset, 0); assert.equal(clip.duration, 2);
  trimRight(clip, 99, 2); assert.equal(clip.start + clip.duration, 3);
});
test('presets support JSON, headered CSV, semicolons with decimal commas and a UTF-8 BOM', () => {
  assert.equal(parsePreset('{"bands":[{"frequency":80,"gain":4,"q":0.7}]}').bands[0].gain, 4);
  assert.equal(parsePreset('\ufefffrequency,gain,q\n80,4,0.7\n8000,-6,1').bands.length, 2);
  const band = parsePreset('frequency;gain;q\n80,5;3,5;0,7').bands[0];
  assert.equal(band.frequency, 80.5); assert.equal(band.gain, 3.5); assert.equal(band.q, .7);
  assert.equal(parsePreset('80,4,0.7').bands[0].frequency, 80);
  const { track } = fixture(); assert.equal(parsePreset(serializePreset(track)).bands.length, 10);
});
test('preset validation rejects invalid frequencies, missing values and excessive bands', () => {
  assert.throws(() => parsePreset('frequency,gain,q\n-1,0,1'), /частота/);
  assert.throws(() => parsePreset('[{"frequency":100,"q":0}]'), /ширина/);
  assert.throws(() => parsePreset('{broken json}'), /JSON/);
  assert.throws(() => parsePreset(JSON.stringify(Array.from({ length: 25 }, () => ({ frequency: 100 })))), /24/);
});
test('project validation checks source boundaries, duplicate ids, missing assets and track limits', () => {
  const { project } = fixture(); assert.equal(validateProject(project).tracks.length, 1);
  const invalid = structuredClone(project); invalid.tracks[0].clips[0].offset = 1;
  assert.throws(() => validateProject(invalid), /границы/);
  const duplicate = structuredClone(project); duplicate.tracks.push(structuredClone(duplicate.tracks[0]));
  assert.throws(() => validateProject(duplicate), /идентификатор/);
  const missing = structuredClone(project); missing.assets = []; assert.throws(() => validateProject(missing), /отсутствующий/);
  const many = createProject(); many.schemaVersion = 1; delete many.soundTypes; many.tracks = Array.from({ length: 51 }, (_, i) => createTrack(i)); assert.throws(() => validateProject(many), /число/);
});
test('history restores edits and clears redo after branching', () => {
  const { project } = fixture(), history = new History(2); history.push(project); project.tracks[0].volume = -9;
  const previous = history.undo(project); assert.equal(previous.tracks[0].volume, 0);
  const next = history.redo(previous); assert.equal(next.tracks[0].volume, -9);
  history.undo(next); history.push(previous); assert.equal(history.future.length, 0);
});
test('solo and mute affect the mix but explicit track preview remains available', () => {
  const { project, track } = fixture(); const other = createTrack(1); project.tracks.push(other);
  other.solo = true; assert.deepEqual(audibleTracks(project).map(item => item.id), [other.id]);
  other.muted = true; assert.equal(audibleTracks(project).length, 0);
  assert.deepEqual(audibleTracks(project, track.id).map(item => item.id), [track.id]);
});
