export function filterAssignments(options, query = '', tab = 'empty') {
  const words = query.trim().toLocaleLowerCase('ru').split(/\s+/).filter(Boolean);
  return options.filter(option => (tab === 'all' || (tab === 'ready') === option.assigned)
    && words.every(word => `${option.name} ${option.hook} ${option.category || ''}`.toLocaleLowerCase('ru').includes(word)));
}

export function assignmentOptions(catalog, type, weapon, scene, node) {
  const events = catalog?.events || [];
  if (type === 'weapon') return events.filter(event => event.weapon === weapon).map(event => ({
    hook: event.binding.hook, name: event.name, category: event.group,
    assigned: event.files.length > 0, eventId: event.id,
  }));
  return (catalog?.actions || []).filter(action => type !== 'object_action' || action.supportsObject).map(action => {
    const event = events.find(event => event.binding.hook === action.hook && (type === 'object_action'
      ? event.binding.type === type && event.binding.scene === scene && event.binding.node === node
      : event.binding.type === 'action'));
    return { ...action, assigned: !!event?.files.length, eventId: event?.id };
  });
}
