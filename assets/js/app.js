'use strict';
const data = window.AUTORSE_DATA;
const $ = (s, root = document) => root.querySelector(s);
const $$ = (s, root = document) => [...root.querySelectorAll(s)];

// All scientific values come from the manuscript, not a live leaderboard.
const taskRows = $('#task-rows');
const taskIcons = {HSTU:'Hs', TIGER:'Ti', IntSR:'Is', WuKong:'Wk', RankMixer:'Rm', OneTrans:'Ot'};
data.tasks.forEach(task => {
  const tr = document.createElement('tr');
  tr.dataset.type = task.type;
  tr.innerHTML = `<td><div class="task-name ${task.type === 'CTR prediction' ? 'ctr' : ''}"><span class="task-icon" aria-hidden="true">${taskIcons[task.name]}</span><span>${task.name}<small class="task-kind">${task.type}</small></span></div></td><td>${task.method}</td><td>${task.dataset}</td><td><span class="metric-tag">${task.metric}</span></td>`;
  taskRows.append(tr);
});
$$('[data-task-filter]').forEach(button => button.addEventListener('click', () => {
  const chosen = button.dataset.taskFilter;
  $$('[data-task-filter]').forEach(b => {b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button));});
  let count = 0;
  [...taskRows.rows].forEach(row => {row.hidden = chosen !== 'all' && row.dataset.type !== chosen; if (!row.hidden) count++;});
  $('#task-count').textContent = chosen === 'all' ? 'Showing all 6 tasks.' : `Showing ${count} ${chosen.toLowerCase()} tasks.`;
}));

let resultMode = 'gain';
const signed = value => `${value < 0 ? '−' : '+'}${Math.abs(value).toFixed(2)}%`;
function renderResults() {
  const result = data.mainResults;
  const harness = $('#harness-filter').value;
  const taskMetric = {HSTU:'NDCG@10', IntSR:'Macro NDCG@10', TIGER:'NDCG@10', OneTrans:'Click AUC', RankMixer:'AUC', WuKong:'AUC'};
  $('#results-head').innerHTML = `<tr><th scope="col">LLM / Harness</th>${result.task_order.map(t => `<th scope="col">${t}<small>${taskMetric[t]}</small></th>`).join('')}<th scope="col">Avg. gain<small>Across six tasks</small></th></tr>`;
  const rows = result.rows.filter(row => harness === 'all' || row.harness === harness);
  const bestScores = result.task_order.map((_, i) => Math.max(...result.rows.map(r => r.scores[i])));
  const baseline = `<tr class="baseline-row"><td>Reference baseline</td>${result.baseline.map(score => `<td>${resultMode === 'gain' ? '—' : score.toFixed(4)}</td>`).join('')}<td>0.00%</td></tr>`;
  $('#results-body').innerHTML = baseline + rows.map(row => `<tr><td><span class="model-label">${row.model}</span><span class="harness-label">${row.harness}</span></td>${row.scores.map((score, i) => {
    const gain = row.relative_gain_percent[i];
    const best = score === bestScores[i] ? ' best' : '';
    return resultMode === 'gain' ? `<td class="${gain >= 0 ? 'gain-positive' : 'gain-negative'}${best}">${signed(gain)}</td>` : `<td class="${best.trim()}">${score.toFixed(4)}<span class="sd">± ${row.sd[i].toFixed(4)}</span></td>`;
  }).join('')}<td class="gain-average ${row.average_gain_percent >= 0 ? 'gain-positive' : 'gain-negative'}">${signed(row.average_gain_percent)}</td></tr>`).join('');
  $('#results-note').textContent = resultMode === 'gain' ? 'Relative change from each task’s baseline. Negative values are shown explicitly. Average gain is the unweighted mean across six tasks. Bold values mark the best result per task across all configurations.' : 'Test scores are mean ± standard deviation across available trials. Bold values mark the best result per task across all configurations. The last column always shows average relative gain.';
}
$$('[data-result-mode]').forEach(button => button.addEventListener('click', () => {
  resultMode = button.dataset.resultMode;
  $$('[data-result-mode]').forEach(b => {b.classList.toggle('active', b === button); b.setAttribute('aria-pressed', String(b === button));});
  renderResults();
}));
$('#harness-filter').addEventListener('change', renderResults);
renderResults();

data.ideas.task_order.forEach((task, index) => {
  const tr = document.createElement('tr');
  tr.innerHTML = `<td>${task}</td><td>${data.ideas.standard_scores[index].toFixed(5)}</td><td>${data.ideas.self_generated_scores[index].toFixed(5)}</td><td>${data.ideas.idea_injected_scores[index].toFixed(5)}</td>`;
  $('#idea-rows').append(tr);
});
data.abstract.forEach(text => {const p = document.createElement('p'); p.textContent = text; $('#abstract-text').append(p);});

const menuButton = $('.menu-toggle');
const navLinks = $('#nav-links');
function closeMenu() {navLinks.classList.remove('open'); menuButton.setAttribute('aria-expanded', 'false'); menuButton.setAttribute('aria-label', 'Open navigation');}
menuButton.addEventListener('click', () => {const isOpen = !navLinks.classList.contains('open'); navLinks.classList.toggle('open', isOpen); menuButton.setAttribute('aria-expanded', String(isOpen)); menuButton.setAttribute('aria-label', isOpen ? 'Close navigation' : 'Open navigation');});
$$('a', navLinks).forEach(link => link.addEventListener('click', closeMenu));
document.addEventListener('keydown', event => {if (event.key === 'Escape' && navLinks.classList.contains('open')) {closeMenu(); menuButton.focus();}});
if ('IntersectionObserver' in window) {
  const observer = new IntersectionObserver(entries => {
    const current = entries.filter(e => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio)[0];
    if (!current) return;
    $$('#nav-links a').forEach(link => {if (link.hash === '#' + current.target.id) link.setAttribute('aria-current', 'location'); else link.removeAttribute('aria-current');});
  }, {rootMargin:'-12% 0px -53% 0px', threshold:[0, .1, .3]});
  $$('section[id]').forEach(section => observer.observe(section));
}

const dialog = $('#figure-dialog'); let returnFocus = null;
$$('[data-zoom]').forEach(button => button.addEventListener('click', () => {
  if (!dialog.showModal) {window.open(button.dataset.zoom, '_blank', 'noopener'); return;}
  returnFocus = button;
  $('#dialog-image').src = button.dataset.zoom;
  $('#dialog-image').alt = $('img', button).alt;
  $('#figure-dialog-caption').textContent = button.dataset.caption;
  $('#dialog-original').href = button.dataset.zoom;
  dialog.showModal(); document.body.style.overflow = 'hidden';
}));
$('#close-figure').addEventListener('click', () => dialog.close());
dialog.addEventListener('click', event => {if (event.target === dialog) {const r = dialog.getBoundingClientRect(); if (event.clientX < r.left || event.clientX > r.right || event.clientY < r.top || event.clientY > r.bottom) dialog.close();}});
dialog.addEventListener('close', () => {document.body.style.overflow = ''; if (returnFocus) returnFocus.focus();});

$('#copy-bib').addEventListener('click', async () => {
  const citation = $('#bibtex').textContent;
  let copied = false;
  try {await navigator.clipboard.writeText(citation); copied = true;} catch (_) {
    const textarea = document.createElement('textarea'); textarea.value = citation; textarea.setAttribute('readonly', ''); textarea.style.cssText = 'position:fixed;left:-9999px;top:0'; document.body.append(textarea); textarea.select();
    try {copied = document.execCommand('copy');} catch (_) {} textarea.remove();
  }
  const button = $('#copy-bib');
  if (copied) {$('span', button).textContent = 'Copied!'; button.classList.add('done'); $('#copy-status').textContent = 'BibTeX citation copied to clipboard.'; setTimeout(() => {$('span', button).textContent = 'Copy citation'; button.classList.remove('done');}, 2200);}
  else {$('#citation-details').open = true; $('#copy-status').textContent = 'Automatic copying is unavailable. The citation is selected; copy it manually.'; const range = document.createRange(); range.selectNodeContents($('#bibtex')); const selection = window.getSelection(); selection.removeAllRanges(); selection.addRange(range);}
});
