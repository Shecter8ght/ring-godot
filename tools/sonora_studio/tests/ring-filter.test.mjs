import { test } from 'node:test';
import assert from 'node:assert/strict';
import { assignmentOptions, filterAssignments } from '../ui/ring-filter.mjs';

const catalog = { actions: [{ hook: 'step_sand', name: 'Шаг по песку' }, { hook: 'door', name: 'Дверь', supportsObject: true }], events: [
  { id: 'sand', name: 'Шаг по песку', files: ['sand.wav'], binding: { type: 'action', hook: 'step_sand' } },
  { id: 'gate', files: ['door.wav'], binding: { type: 'object_action', hook: 'door', scene: 'warehouse', node: 'Gate' } },
  { id: 'pm', weapon: 'pm', name: 'Затвор', files: [], binding: { type: 'action', hook: 'pm_bolt' } },
] };
test('new assignments hide assigned actions by default; tabs and Russian multiword search work', () => {
  const options = assignmentOptions(catalog, 'action');
  assert.deepEqual(filterAssignments(options).map(o => o.hook), ['door']);
  assert.deepEqual(filterAssignments(options, 'песку шаг', 'ready').map(o => o.eventId), ['sand']);
  assert.equal(filterAssignments(options, '', 'all').length, 2);
});
test('assignments on one door do not hide the same action on a different door', () => {
  assert.equal(filterAssignments(assignmentOptions(catalog, 'object_action', '', 'warehouse', 'Gate')).length, 0);
  assert.equal(filterAssignments(assignmentOptions(catalog, 'object_action', '', 'warehouse', 'Other')).length, 1);
  assert.equal(filterAssignments(assignmentOptions(catalog, 'weapon', 'pm')).length, 1);
});
