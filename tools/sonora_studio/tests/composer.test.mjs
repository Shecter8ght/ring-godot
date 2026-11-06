import { test } from 'node:test';
import assert from 'node:assert/strict';
import { createProject, createTrack, createClip, uid, activeTracks, enabledTracks, audibleTracks, visibleTracks, projectEnd, currentSoundType, addLayer, assignVariant, newCombination, normalizeWorkbench, validateProject, splitClip, MAX_LAYERS, MAX_VARIANTS } from '../ui/model.mjs';
import { retimeClip, trackSpeed } from '../ui/speed-model.mjs';

function variant(project, layer, name, duration = 1) {
  const asset = { id: uid(), name: name + '.wav', duration, channels: 1, sampleRate: 48000 };
  project.assets.push(asset);
  const track = createTrack(project.tracks.length, name); track.clips = [createClip(asset)];
  const type = project.soundTypes.find(type => type.layers.includes(layer));
  assignVariant(project, track, layer, type);
  return track;
}
test('each sound type builds one mix; hidden variants and hidden solo tracks never enter it', () => {
  const project = createProject(), [body, clap] = currentSoundType(project).layers;
  const a = variant(project, body, 'body A', 10), b = variant(project, body, 'body B', 2), c = variant(project, clap, 'clap', 3);
  const voice = variant(project, project.soundTypes[3].layers[0], 'voice', 100);
  a.solo = voice.solo = true;
  assert.deepEqual(activeTracks(project).map(track => track.id), [b.id, c.id]);
  assert.deepEqual(audibleTracks(project).map(track => track.id), [b.id, c.id]);
  assert.equal(projectEnd(project), 3);
  assert.deepEqual(visibleTracks(project, body.id).map(track => track.id), [b.id]);
  assert.equal(audibleTracks(project).length, 2);
  body.enabled = false; assert.deepEqual(enabledTracks(project).map(track => track.id), [c.id]);
  assert.deepEqual(audibleTracks(project, b.id).map(track => track.id), [b.id]);
  project.activeSoundTypeId = 'voices'; assert.deepEqual(activeTracks(project).map(track => track.id), [voice.id]);
});
test('new combinations change only unlocked enabled layers and never choose the same variant', () => {
  const project = createProject(), [a, b, c] = currentSoundType(project).layers;
  for (const layer of [a, b, c]) { variant(project, layer, 'one'); variant(project, layer, 'two'); }
  b.locked = true; c.enabled = false;
  const before = [a, b, c].map(layer => layer.activeVariantId);
  assert.equal(newCombination(project, () => 0), 1);
  assert.notEqual(a.activeVariantId, before[0]); assert.equal(b.activeVariantId, before[1]); assert.equal(c.activeVariantId, before[2]);
  assert.doesNotThrow(() => validateProject(project));
});
test('legacy projects with 50 tracks migrate without losing their parallel mix or effects', () => {
  const project = createProject(); project.schemaVersion = 1; delete project.soundTypes; delete project.activeSoundTypeId;
  project.tracks = Array.from({ length: 50 }, (_, i) => createTrack(i));
  project.tracks[0].volume = -12; project.tracks[1].fx.reverb.enabled = true;
  const expected = structuredClone(project.tracks), checked = validateProject(project);
  assert.equal(checked.schemaVersion, 3); assert.equal(currentSoundType(checked).layers.length, 50);
  assert.equal(activeTracks(checked).length, 50);
  assert.equal(checked.tracks[0].volume, -12); assert.equal(checked.tracks[1].fx.reverb.enabled, true);
  checked.tracks.forEach((track, i) => { assert.equal(track.id, expected[i].id); assert.deepEqual(track.clips, expected[i].clips); });
  assert.doesNotThrow(() => validateProject(checked));
});
test('speed changes preserve edits and original source through cuts and repeated absolute speeds', () => {
  const original = { id: uid(), name: 'bolt.wav', duration: 4 }, fast = { id: uid(), duration: 1 };
  const clip = { ...createClip(original, .4), offset: 1, duration: 2, fadeIn: .02, fadeOut: .04, gain: -3 };
  const faster = retimeClip(clip, fast, 4), track = createTrack(); track.clips = [faster];
  assert.equal(faster.start, .4); assert.equal(faster.duration, .5); assert.equal(faster.offset, .25);
  assert.equal(faster.sourceAssetId, original.id); assert.equal(faster.gain, -3); assert.equal(trackSpeed(track), 4);
  const right = splitClip(track, faster.id, .65); assert.ok(right);
  const restored = retimeClip(right, original, 1);
  assert.equal(restored.offset, 2); assert.equal(restored.duration, 1); assert.equal(restored.start, .65);
  assert.equal(restored.assetId, original.id); assert.equal(restored.sourceAssetId, original.id);
  assert.equal(restored.fadeOut, .04); assert.equal(restored.fadeIn, 0);
  track.clips[1] = restored; assert.equal(trackSpeed(track), null);
});
test('project validation rejects foreign variants, missing speed sources and invalid rates', () => {
  const project = createProject(), [a, b] = currentSoundType(project).layers;
  variant(project, a, 'body'); const second = variant(project, b, 'clap');
  const bad = structuredClone(project); bad.soundTypes[0].layers[0].activeVariantId = second.id;
  assert.throws(() => validateProject(bad), /варианты/);
  const missing = structuredClone(project); missing.tracks[0].clips[0].sourceAssetId = uid();
  assert.throws(() => validateProject(missing), /Исходник/);
  const rate = structuredClone(project); rate.tracks[0].clips[0].speed = 20;
  assert.throws(() => validateProject(rate), /скорость/);
});
test('limits allow 50 parallel layers and multiple variants, and orphan workshop tracks are adopted', () => {
  const project = createProject(), type = currentSoundType(project); type.layers = [];
  for (let i = 0; i < MAX_LAYERS; i++) addLayer(project, 'Layer ' + i);
  assert.throws(() => addLayer(project, 'overflow'), /50/);
  for (let i = 0; i < MAX_VARIANTS; i++) assignVariant(project, createTrack(i), type.layers[0]);
  assert.throws(() => assignVariant(project, createTrack(), type.layers[0]), /32/);
  assert.equal(activeTracks(project).length, 1);
  type.layers.pop(); const orphan = createTrack(); project.tracks.push(orphan); normalizeWorkbench(project);
  assert.ok(orphan.layerId); assert.equal(activeTracks(project).length, 2);
  assert.doesNotThrow(() => validateProject(project));
});
