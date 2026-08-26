// Draws docs/data/eval.json, which scripts/make_page_data.py produces by
// importing the repository's own classifiers and re-running them over
// icp_eval.csv. Nothing here recomputes a metric; the page only arranges them.

const el = (id) => document.getElementById(id);
const css = (n) => getComputedStyle(document.documentElement).getPropertyValue(n).trim();

const state = { data: null, clf: 'rules_v2', cost: '0.1' };

const LABELS = {
  enrich_all: 'Enrich everything',
  industry_tag: 'Industry tag',
  rules: 'Rules',
  rules_v2: 'Rules v2',
};
const AXIS_LABELS = { is_b2b: 'is it B2B', is_saas: 'is it SaaS', stage_fit: 'right stage' };

const pick = () => state.data.classifiers.find((c) => c.name === state.clf);
const usd = (v) => `$${v.toFixed(3)}`;

function fitCanvas(canvas, h0) {
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const w0 = canvas.clientWidth || 1200;
  canvas.width = Math.round(w0 * dpr);
  canvas.height = Math.round(h0 * dpr);
  canvas.style.height = h0 + 'px';
  const ctx = canvas.getContext('2d');
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w0, h0);
  return { ctx, w: w0, h: h0 };
}

function confusion() {
  const c = pick();
  const cell = (v, label, cls) =>
    `<div><div class="v ${cls}">${v}<small>${label}</small></div></div>`;
  el('cm').innerHTML =
    '<div class="lab"></div><div class="lab">it said yes</div><div class="lab">it said no</div>' +
    '<div class="lab">really ICP</div>' +
    cell(c.tp, 'found', 'hit') +
    cell(c.fn, 'missed', c.fn ? 'miss' : '') +
    '<div class="lab">not ICP</div>' +
    cell(c.fp, 'wasted calls', c.fp ? 'miss' : '') +
    cell(c.tn, 'correctly skipped', '');
}

function render() {
  const c = pick();
  const d = state.data;
  el('r-prec').textContent = `${(c.precision * 100).toFixed(1)}%`;
  el('r-rec').textContent = `${(c.recall * 100).toFixed(1)}%`;
  el('r-f1').textContent = c.f1.toFixed(3);
  el('r-enr').textContent = `${c.enriched} of ${d.n}`;
  el('r-found').textContent = `${c.found} of ${d.positives}`;
  el('cap-what').textContent = `${d.n} companies, ${d.positives} really ICP, ${d.borderline} borderline`;
  el('cap-src').textContent = d.source;
  confusion();

  const b = el('banner');
  if (c.recall === 1 && c.precision < 0.5) {
    b.className = 'banner alarm';
    b.textContent =
      `It finds every real customer and it enriches ${c.enriched} leads to do it. ` +
      `${(c.precision * 100).toFixed(0)}% of those calls were worth making.`;
  } else if (c.recall < 0.6) {
    b.className = 'banner alarm';
    b.textContent =
      `Right ${(c.precision * 100).toFixed(1)}% of the times it says yes, and it says no to ` +
      `${c.fn} of the ${d.positives} real customers. Precision this high is bought with them.`;
  } else {
    b.className = 'banner calm';
    b.textContent =
      `${c.found} of ${d.positives} real customers found, at ${c.fp} wasted enrichment calls ` +
      `and ${c.fn} missed. F1 ${c.f1.toFixed(3)}.`;
  }
  axes();
  errors();
}

function drawCost() {
  const rows = state.data.classifiers;
  const { ctx, w, h } = fitCanvas(el('plot'), 200);
  const pad = { l: 172, r: 92, t: 16, b: 34 };
  const iw = w - pad.l - pad.r;
  const top = Math.max(...rows.map((c) => c.cost_per_resolved[state.cost])) * 1.06;
  const rowH = (h - pad.t - pad.b) / rows.length;
  const barH = Math.min(rowH * 0.6, 24);
  const X = (v) => pad.l + (v / top) * iw;

  rows.forEach((c, i) => {
    const y = pad.t + i * rowH + (rowH - barH) / 2;
    const v = c.cost_per_resolved[state.cost];
    ctx.fillStyle = css('--ox');
    ctx.fillRect(pad.l, y, Math.max(X(v) - pad.l, 1), barH);
    if (c.name === state.clf) {
      ctx.strokeStyle = css('--ink');
      ctx.lineWidth = 2;
      ctx.strokeRect(pad.l - 2, y - 2, Math.max(X(v) - pad.l, 1) + 4, barH + 4);
    }
    ctx.textAlign = 'right';
    ctx.font = "13px 'Times New Roman', serif";
    ctx.fillStyle = c.name === state.clf ? css('--ink') : css('--sub');
    ctx.fillText(LABELS[c.name] || c.name, pad.l - 10, y + barH / 2 + 4);
    ctx.textAlign = 'left';
    ctx.fillStyle = css('--sub');
    ctx.fillText(`${usd(v)}  (${c.found}/${state.data.positives} found)`, X(v) + 8, y + barH / 2 + 4);
  });

  ctx.textAlign = 'left';
  ctx.fillStyle = css('--faint');
  ctx.font = "11px 'Courier New', monospace";
  ctx.fillText('cost per real customer found, at the selected price per call', pad.l, h - 10);
}

function renderCost() {
  el('cap-cost').textContent = `$${Number(state.cost).toFixed(2)} per enrichment call, an assumption`;
  drawCost();
  const rows = state.data.classifiers;
  const best = rows.reduce((a, b) =>
    b.cost_per_resolved[state.cost] < a.cost_per_resolved[state.cost] ? b : a);
  const all = rows.find((c) => c.name === 'enrich_all');
  el('cost-banner').className = 'banner calm';
  el('cost-banner').textContent =
    `Cheapest per customer found: ${LABELS[best.name]} at ${usd(best.cost_per_resolved[state.cost])}, ` +
    `against ${usd(all.cost_per_resolved[state.cost])} for enriching every lead. It finds ` +
    `${best.found} of ${state.data.positives}.`;
}

function axes() {
  const c = pick();
  const rows = Object.entries(c.axes || {});
  if (!rows.length) {
    el('axes').innerHTML = '';
    el('cap-axis').textContent = 'this filter does not decide the axes separately';
    return;
  }
  el('cap-axis').textContent = `per-axis agreement, ${LABELS[c.name] || c.name}`;
  const worst = rows.reduce((a, b) => (b[1].f1 < a[1].f1 ? b : a));
  const head = '<tr><th>axis</th><th>F1</th><th>precision</th><th>recall</th><th>missed</th><th>wrongly said yes</th></tr>';
  const body = rows
    .map(
      ([k, v]) =>
        `<tr><td class="name">${AXIS_LABELS[k] || k}</td>` +
        `<td class="num ${k === worst[0] ? 'bad' : ''}">${v.f1.toFixed(3)}</td>` +
        `<td class="num">${v.precision.toFixed(3)}</td><td class="num">${v.recall.toFixed(3)}</td>` +
        `<td class="num">${v.fn}</td><td class="num">${v.fp}</td></tr>`,
    )
    .join('');
  el('axes').innerHTML = `<thead>${head}</thead><tbody>${body}</tbody>`;
}

function errors() {
  const c = pick();
  // Capped, and the cap is stated rather than left to look like the whole list.
  const CAP = 20;
  const shown = c.errors.slice(0, CAP);
  el('cap-errs').textContent =
    c.errors.length > CAP
      ? `${CAP} of ${c.errors.length} mistakes shown`
      : `all ${c.errors.length} mistakes`;
  el('errs').innerHTML = shown
    .map((e) => {
      const disagree = Object.entries(e.axes)
        .filter(([, v]) => v.gold !== v.pred)
        .map(([k, v]) => `<em>${AXIS_LABELS[k] || k}</em>: labelled ${v.gold ? 'yes' : 'no'}, called ${v.pred ? 'yes' : 'no'}`)
        .join('; ');
      return (
        `<div class="err"><b>${e.name}</b>` +
        `<span class="kind ${e.kind}">${e.kind === 'missed' ? 'missed customer' : 'wasted call'}` +
        `${e.borderline ? ', borderline' : ''}</span>` +
        `<span class="why">${e.one_liner}${disagree ? `<br>${disagree}` : ''}</span></div>`
      );
    })
    .join('');
  const missed = c.errors.filter((e) => e.kind === 'missed').length;
  el('err-banner').className = 'banner';
  const wasted = c.errors.length - missed;
  const border = c.errors.filter((e) => e.borderline).length;
  const plural = (n, one, many) => `${n} ${n === 1 ? one : many}`;
  el('err-banner').textContent =
    `${plural(missed, 'missed customer', 'missed customers')} and ` +
    `${plural(wasted, 'wasted call', 'wasted calls')}. ` +
    (border
      ? `${border} of them are rows labelled borderline on purpose.`
      : 'None of them are rows labelled borderline on purpose.');
}

function picker(node, items, current, onPick) {
  node.innerHTML = '';
  items.forEach(({ key, label }) => {
    const b = document.createElement('button');
    b.textContent = label;
    b.setAttribute('aria-pressed', String(key === current()));
    b.addEventListener('click', () => {
      onPick(key);
      [...node.children].forEach((c) => c.setAttribute('aria-pressed', String(c === b)));
    });
    node.appendChild(b);
  });
}

async function main() {
  const res = await fetch('./data/eval.json');
  if (!res.ok) {
    el('banner').textContent = `Could not load the evaluation (HTTP ${res.status}).`;
    return;
  }
  state.data = await res.json();

  picker(
    el('clf'),
    state.data.classifiers.map((c) => ({ key: c.name, label: LABELS[c.name] || c.name })),
    () => state.clf,
    (k) => { state.clf = k; render(); renderCost(); },
  );
  picker(
    el('cost'),
    state.data.unit_costs.map((c) => ({ key: String(c), label: `$${c.toFixed(2)}` })),
    () => state.cost,
    (k) => { state.cost = k; renderCost(); },
  );
  window.addEventListener('resize', drawCost);

  render();
  renderCost();
}

main();
