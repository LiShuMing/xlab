/* Optional, scoped enhancement. Evidence is text/data attributes, never eval. */
(() => {
  'use strict';
  for (const root of document.querySelectorAll('[data-report-explorer]')) {
    const table = root.querySelector('table[data-report-table]');
    const body = table?.tBodies[0];
    if (!body) continue;
    const rows = Array.from(body.rows);
    const originalOrder = new Map(rows.map((row, index) => [row, index]));
    const search = root.querySelector('[data-report-search]');
    const filters = Array.from(root.querySelectorAll('[data-report-filter]'));
    const sort = root.querySelector('[data-report-sort]');
    const controls = [search, ...filters, sort].filter(Boolean);
    const defaults = new Map(controls.map(control => [control, control.value]));
    const count = root.querySelector('[data-report-count]');
    function numeric(row, key) {
      const raw = row.dataset[key];
      if (raw == null || raw.trim() === '') return null;
      const value = Number(raw);
      return Number.isFinite(value) ? value : null;
    }
    function update() {
      const text = (search?.value || '').trim().toLocaleLowerCase();
      const [key, direction] = (sort?.value || '').split(':');
      const ordered = [...rows].sort((a, b) => {
        if (!key) return originalOrder.get(a) - originalOrder.get(b);
        const av = numeric(a, key), bv = numeric(b, key);
        if (av === null && bv !== null) return 1;
        if (bv === null && av !== null) return -1;
        if (av !== null && bv !== null && av !== bv) return (av - bv) * (direction === 'desc' ? -1 : 1);
        return originalOrder.get(a) - originalOrder.get(b);
      });
      let visible = 0;
      const fragment = document.createDocumentFragment();
      for (const row of ordered) {
        const haystack = (row.dataset.search ?? row.textContent).toLocaleLowerCase();
        row.hidden = !haystack.includes(text) || filters.some(control => {
          const selected = control.value;
          return selected !== 'all' && !(row.dataset[control.dataset.reportFilter] || '').split(/\s+/).includes(selected);
        });
        if (!row.hidden) visible++;
        fragment.appendChild(row);
      }
      body.appendChild(fragment);
      if (count) count.textContent = `显示 ${visible} / ${rows.length} 条；筛选不改变全局合计口径。`;
    }
    for (const control of controls) control.addEventListener(control === search ? 'input' : 'change', update);
    root.querySelector('[data-report-reset]')?.addEventListener('click', () => {
      for (const control of controls) control.value = defaults.get(control);
      update();
    });
    update();
  }
  function reveal() {
    let id;
    try { id = decodeURIComponent(location.hash.slice(1)); } catch { return; }
    const node = document.getElementById(id);
    if (!node) return;
    for (let p = node; p; p = p.parentElement) if (p.tagName === 'DETAILS') p.open = true;
    const detail = node.querySelector(':scope > details');
    if (detail) detail.open = true;
    requestAnimationFrame(() => node.scrollIntoView({ block: 'start' }));
  }
  document.addEventListener('click', event => {
    const link = event.target.closest?.('a[href^="#"]');
    if (link && link.hash === location.hash) reveal();
  });
  addEventListener('hashchange', reveal);
  reveal();
})();
