import { test } from 'node:test';
import assert from 'node:assert/strict';
import { analyzeShot, splitShot, planShot } from '../ui/shot-analysis.mjs';
import { defaultShotDesign, validateShotDesign, shotTail } from '../ui/shot-model.mjs';
import { createProject, createTrack, validateProject, assignVariant } from '../ui/model.mjs';
function recordedShot(gain = 1) {
  const rate = 48000, channels = [new Float32Array(rate), new Float32Array(rate)]; let state = 293;
  for (let i = 4800; i < rate; i++) { state = (Math.imul(state, 1664525) + 1013904223) | 0; const t = (i - 4800) / rate, value = .5 * Math.sin(2 * Math.PI * 120 * t) * Math.exp(-t * 24) + .25 * ((state >>> 0) / 2147483648 - 1) * Math.exp(-t * 12); channels[0][i] = value * gain; channels[1][i] = value * gain * .4; }
  return channels;
}
test('five complementary extracted layers reconstruct the source and stereo exactly within float precision', () => {
  const input = recordedShot(), result = splitShot(input, 48000); let maximum = 0;
  for (let c = 0; c < 2; c++) for (let i = 0; i < input[c].length; i++) {
    const sum = Object.values(result.layers).reduce((value, data) => value + data[c][i], 0); maximum = Math.max(maximum, Math.abs(sum - input[c][i]));
  }
  assert.ok(maximum < 1e-7); assert.ok(Math.abs(result.analysis.onset - .1) < .002); assert.ok(result.analysis.bodyEnd > .15 && result.analysis.bodyEnd < .27);
  for (const part of Object.values(result.layers)) { let energy = 0; for (let i = 0; i < part[0].length; i++) { energy += part[0][i] ** 2; assert.ok(Math.abs(part[1][i] - part[0][i] * .4) < 5e-8); } assert.ok(energy > 0); }
});
test('onset and body detection tolerate overall recording levels and reject silence', () => {
  const loud = analyzeShot(recordedShot(), 48000), quiet = analyzeShot(recordedShot(.003), 48000);
  assert.equal(loud.onset, quiet.onset); assert.equal(loud.bodyEnd, quiet.bodyEnd); assert.ok(Math.abs(loud.peakDb - quiet.peakDb + 20 * Math.log10(.003)) < .001);
  assert.throws(() => analyzeShot([new Float32Array(480)], 48000), /бесшумный/);
});
test('environment tails differ, bypass and zero reflections add no tail, and parameters are bounded', () => {
  const project = createProject(), design = project.soundTypes[0].shotDesign; assert.equal(shotTail(project), 0);
  Object.assign(design, { enabled: true, environment: 'small' }); const small = shotTail(project);
  design.environment = 'large'; assert.ok(shotTail(project) > small * 3);
  design.environment = 'outdoor'; assert.ok(shotTail(project) < small);
  design.amount = 0; assert.equal(shotTail(project), 0);
  for (const input of [{ environment: 'unknown' }, { amount: Infinity }, { suppression: -1 }, { size: 100 }, { output: 24 }]) assert.throws(() => validateShotDesign(input));
});
test('schema 2 projects migrate with neutral shared processing and preserve the old mix', () => {
  const project = createProject(), track = createTrack(); assignVariant(project, track, project.soundTypes[0].layers[0]);
  project.schemaVersion = 2; for (const type of project.soundTypes) { delete type.shotDesign; for (const layer of type.layers) delete layer.role; }
  const migrated = validateProject(project); assert.equal(migrated.schemaVersion, 3); assert.deepEqual(migrated.soundTypes[0].shotDesign, defaultShotDesign()); assert.equal(migrated.soundTypes[0].layers[0].role, 'low'); assert.equal(migrated.tracks[0].id, track.id);
});
test('timing plan places trigger before the shot, links bolt/casing timing, retains locks and pitch-safe speed bounds', () => {
  const stats = { onset: .02, activeDuration: .5, peakDb: -12 };
  const entries = ['low','trigger','pin','boltBack','boltForward','casing'].map((role,i) => ({ trackId:String(i), role, start:0, stats, volume:0, speed:1, locked:role === 'casing' }));
  const plan = planShot(entries); const byRole = role => plan.rows.find(item => item.role === role);
  assert.equal(plan.rows.length, 5); assert.equal(plan.skipped, 1);
  for (const row of plan.rows) assert.ok(row.start + row.delta >= 0);
  const eventTime = row => row.start + row.delta + row.stats.onset / row.rate;
  assert.ok(eventTime(byRole('trigger')) < eventTime(byRole('low')));
  assert.ok(Math.abs(eventTime(byRole('boltForward')) - eventTime(byRole('low')) - .068) < .001);
  assert.equal(byRole('pin').rate, 8); assert.ok(byRole('boltBack').volume < 0);
});
test('derived bands remain synchronous and keep their levels under an automatic scenario', () => {
  const entries = ['low','mid','high','gas','tail'].map((role,i) => ({ trackId:String(i), role, start:.1, stats:{onset:i*.01,activeDuration:.5,peakDb:-10-i}, volume:0, speed:1, originOnset:.02 }));
  const plan = planShot(entries); assert.equal(new Set(plan.rows.map(row => row.delta)).size, 1);
  assert.ok(plan.rows.every(row => row.volume === 0 && row.rate === 1));
});
