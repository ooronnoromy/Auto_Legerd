const {test} = require('node:test');
const assert = require('node:assert/strict');
const {readFileSync} = require('node:fs');
const {runInNewContext} = require('node:vm');

function fixture() {
  const handlers = {};
  let fieldFocused = 0, triggerFocused = 0;
  const trigger = {focus() {triggerFocused++;}};
  const input = {focus() {fieldFocused++;}};
  const close = {addEventListener(name, fn) {handlers[`close:${name}`] = fn;}};
  const search = {
    open: false,
    querySelector(selector) {return selector === 'summary' ? trigger : selector.includes('input') ? input : close;},
    addEventListener(name, fn) {handlers[`search:${name}`] = fn;},
    contains(target) {return target === input || target === trigger || target === close;},
  };
  const active = {offsetLeft: 500, offsetWidth: 100};
  const nav = {scrollLeft: 0, clientWidth: 300, querySelector() {return active;}};
  const document = {
    getElementById() {return search;},
    querySelector() {return nav;},
    addEventListener(name, fn) {handlers[`document:${name}`] = fn;},
  };
  runInNewContext(readFileSync('static/js/glass.js', 'utf8'), {document});
  return {search, input, trigger, nav, handlers, focused: () => ({fieldFocused, triggerFocused})};
}

test('opening search focuses the field; closing returns focus to its icon', () => {
  const f = fixture();
  f.search.open = true;
  f.handlers['search:toggle']();
  assert.equal(f.focused().fieldFocused, 1);
  f.handlers['close:click']();
  assert.equal(f.search.open, false);
  assert.equal(f.focused().triggerFocused, 1);
});

test('Escape dismisses search and restores focus, while closed search leaves Escape alone', () => {
  const f = fixture();
  let prevented = 0;
  const event = {key: 'Escape', preventDefault() {prevented++;}};
  f.search.open = true;
  f.handlers['document:keydown'](event);
  assert.equal(f.search.open, false);
  assert.equal(f.focused().triggerFocused, 1);
  f.handlers['document:keydown'](event);
  assert.equal(prevented, 1);
});

test('clicking inside search keeps it open; clicking outside dismisses it without stealing focus', () => {
  const f = fixture();
  f.search.open = true;
  f.handlers['document:click']({target: f.input});
  assert.equal(f.search.open, true);
  f.handlers['document:click']({target: {}});
  assert.equal(f.search.open, false);
  assert.equal(f.focused().triggerFocused, 0);
});

test('slash opens search but does not intercept typing in fields or browser shortcuts', () => {
  const f = fixture();
  let prevented = 0;
  const event = {key: '/', target: {closest: () => null}, preventDefault() {prevented++;}};
  f.handlers['document:keydown'](event);
  assert.equal(f.search.open, true);
  assert.equal(prevented, 1);
  f.search.open = false;
  f.handlers['document:keydown']({...event, target: {closest: () => ({})}});
  f.handlers['document:keydown']({...event, ctrlKey: true});
  f.handlers['document:keydown']({...event, metaKey: true});
  f.handlers['document:keydown']({...event, altKey: true});
  assert.equal(f.search.open, false);
  assert.equal(prevented, 1);
});

test('the selected mobile destination is scrolled into view without moving the page', () => {
  const f = fixture();
  assert.equal(f.nav.scrollLeft, 400);
});

test('pages without search do not register global handlers', () => {
  runInNewContext(readFileSync('static/js/glass.js', 'utf8'), {
    document: {getElementById: () => null, addEventListener() {assert.fail('unexpected handler');}},
  });
});
