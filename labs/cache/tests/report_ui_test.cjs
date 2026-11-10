// Exercise the shipped offline filtering/sorting code with a minimal DOM, without npm.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
const vm = require('node:vm');
function control(value, dataset = {}) {
  return { value, dataset, events: {}, addEventListener(name, fn) { this.events[name] = fn; } };
}
const rows = [
  { dataset: { ns: '10', delta: '-50', algorithm: 'slru' }, textContent: 'slru scan_mix', hidden: false },
  { dataset: { ns: '2', delta: '20', algorithm: 'lru' }, textContent: 'lru uniform', hidden: false },
  { dataset: { ns: '', delta: '', algorithm: 'wtinylfu' }, textContent: 'wtinylfu scan_mix', hidden: false },
];
const search = control('');
const filter = control('all', { reportFilter: 'algorithm' });
const sort = control('');
const reset = control('');
const count = { textContent: '' };
const body = { rows, appendChild(fragment) { this.rows = fragment.children; } };
const controls = {
  'table[data-report-table]': { tBodies: [body] }, '[data-report-search]': search,
  '[data-report-sort]': sort, '[data-report-count]': count, '[data-report-reset]': reset,
};
const root = { querySelector: key => controls[key], querySelectorAll: () => [filter] };
const document = {
  querySelectorAll: () => [root],
  createDocumentFragment: () => ({ children: [], appendChild(row) { this.children.push(row); } }),
  getElementById: () => null, addEventListener() {},
};
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../assets/report.js'), 'utf8'), {
  document, location: { hash: '' }, addEventListener() {}, requestAnimationFrame: fn => fn(),
});
search.value = 'scan_mix'; search.events.input();
assert.equal(body.rows.filter(row => !row.hidden).length, 2);
filter.value = 'slru'; filter.events.change();
assert.equal(body.rows.filter(row => !row.hidden).length, 1);
search.value = 'no matching row'; search.events.input();
assert.equal(body.rows.filter(row => !row.hidden).length, 0);
reset.events.click();
assert.equal(body.rows.filter(row => !row.hidden).length, 3);
sort.value = 'ns:asc'; sort.events.change();
assert.deepEqual(body.rows.map(row => row.dataset.ns), ['2', '10', '']);
sort.value = 'delta:asc'; sort.events.change();
assert.deepEqual(body.rows.map(row => row.dataset.delta), ['-50', '20', '']);
sort.value = 'delta:desc'; sort.events.change();
assert.deepEqual(body.rows.map(row => row.dataset.delta), ['20', '-50', '']);
assert.match(count.textContent, /3 \/ 3/);
console.log('PASS: search, algorithm filter, no matches, reset, numeric/negative sort, missing values');
