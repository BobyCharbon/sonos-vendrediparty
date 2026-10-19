// Run with: node --test tests/game_audio.test.cjs
const { test } = require('node:test');
const assert = require('node:assert/strict');
const vm = require('node:vm');
const fs = require('node:fs');
function setup({ blocked = false, unsupported = false } = {}) {
  const listeners = {}, notes = [], stopped = [], storage = new Map();
  const context = {
    document: { hidden: false, addEventListener: (name, fn) => listeners[name] = fn, querySelectorAll: () => [] },
    localStorage: { getItem: k => { if (blocked) throw Error(); return storage.get(k); }, setItem: (k, v) => { if (blocked) throw Error(); storage.set(k, v); } },
    window: {},
  };
  if (!unsupported) context.window.AudioContext = class {
    state = 'running'; currentTime = 0;
    createOscillator() { return { frequency: { setValueAtTime: f => notes.push(f) }, connect() {}, disconnect() {}, start() {}, stop() { stopped.push(true); } }; }
    createGain() { return { gain: { setValueAtTime() {}, linearRampToValueAtTime() {}, exponentialRampToValueAtTime() {} }, connect() {}, disconnect() {} }; }
  };
  vm.createContext(context);
  vm.runInContext(fs.readFileSync('app/static/game-audio.js', 'utf8') + '\nthis.audio = GameAudio;', context);
  const g = { id: 'one', type: 'president', phase: 'lobby', round: 0 };
  context.audio.observe(g, ''); listeners.pointerdown();
  return { ...context, listeners, notes, stopped, storage, g };
}
test('transitions sound once, polling and reconnection stay silent', () => {
  const { audio, notes, g } = setup();
  const play = { ...g, phase: 'play', round: 1 };
  audio.observe(play, 'turn1'); assert.equal(notes.length, 3);
  audio.observe(play, 'turn1'); assert.equal(notes.length, 3);
  audio.observe(play, 'turn2'); assert.equal(notes.length, 5);
  audio.observe(null, ''); audio.observe(play, 'turn2'); assert.equal(notes.length, 5);
});
test('mute persists and stops sounds; hidden document stays silent', () => {
  const s = setup();
  s.audio.play('win'); assert.equal(s.notes.length, 4);
  s.listeners.click({ target: { closest: () => true } });
  assert.equal(s.storage.get('vp-game-sounds'), 'off');
  s.audio.play('win'); assert.equal(s.notes.length, 4);
  assert.ok(s.stopped.length);
  s.listeners.click({ target: { closest: () => true } });
  s.document.hidden = true;
  const count = s.notes.length; s.audio.play('win'); assert.equal(s.notes.length, count);
});
test('countdown only ticks once per second in last five seconds', () => {
  const { audio, notes } = setup();
  [8, 5, 4.9, 4.5, 4, 0, -1].forEach(n => audio.tick('question1', n));
  assert.equal(notes.length, 2);
});
test('storage restrictions and unavailable audio do not prevent playing', () => {
  const s = setup({ blocked: true, unsupported: true });
  s.audio.play('win');
  s.listeners.click({ target: { closest: () => true } });
  assert.equal(s.notes.length, 0);
});
