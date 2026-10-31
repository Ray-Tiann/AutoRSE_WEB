/* Audited aggregate measurements; native SVG and DOM, no chart dependencies. */
(() => {
  'use strict';
  const root = document.getElementById('novelty-explorer');
  if (!root) return;
  root.classList.add('is-loading');
  const $ = selector => root.querySelector(selector);
  const taskSelect = $('[data-ns-task]');
  const agentSelect = $('[data-ns-agent]');
  const chart = $('[data-ns-chart]');
  const inspection = $('[data-ns-inspection]');
  const ns = 'http://www.w3.org/2000/svg';
  const xDomain = [1.5, 3.5];
  const yDomain = [-25, 105];
  const taskOrder = ['HSTU', 'IntSR', 'TIGER', 'OneTrans', 'RankMixer', 'WuKong'];
  let points = [];
  let visible = [];
  let selectedId = null;
  let tabStopId = null;
  let geometry;
  let pointNodes = [];
  let resizeFrame;

  const agentName = point => `${point.harness} × ${point.model}`;
  const number = value => value.toFixed(3).replace(/0+$/, '').replace(/\.$/, '');
  const gain = value => `${value > 0 ? '+' : value < 0 ? '−' : ''}${Math.abs(value).toFixed(2)}%`;
  function svgNode(tag, attrs = {}, text) {
    const node = document.createElementNS(ns, tag);
    Object.entries(attrs).forEach(([name, value]) => node.setAttribute(name, value));
    if (text !== undefined) node.textContent = text;
    return node;
  }
  function textNode(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    node.textContent = text;
    return node;
  }
  function statistics(rows) {
    if (rows.length < 3) return null;
    const mx = rows.reduce((sum, p) => sum + p.novelty, 0) / rows.length;
    const my = rows.reduce((sum, p) => sum + p.gain_percent, 0) / rows.length;
    let xx = 0, yy = 0, xy = 0;
    rows.forEach(p => {
      const dx = p.novelty - mx;
      const dy = p.gain_percent - my;
      xx += dx * dx; yy += dy * dy; xy += dx * dy;
    });
    if (xx <= Number.EPSILON || yy <= Number.EPSILON) return null;
    const slope = xy / xx;
    return {r: Math.max(-1, Math.min(1, xy / Math.sqrt(xx * yy))), slope, intercept: my - slope * mx};
  }
  function updateInspection(point) {
    inspection.hidden = !point;
    if (!point) { inspection.replaceChildren(); return; }
    const identity = textNode('div', 'ns-identity', '');
    identity.append(textNode('strong', '', point.task), textNode('span', '', agentName(point)));
    const values = textNode('div', 'ns-values', '');
    [['Novelty', number(point.novelty)], ['Test gain', gain(point.gain_percent)]].forEach(([label, value]) => {
      const item = textNode('span', '', label);
      item.append(textNode('strong', '', value));
      values.append(item);
    });
    inspection.replaceChildren(identity, values);
  }
  function selectPoint(point, focus = false) {
    const nextId = point?.id ?? null;
    const changed = selectedId !== nextId;
    selectedId = nextId;
    if (point && focus) tabStopId = point.id;
    pointNodes.forEach(({point: p, node}) => {
      const active = p.id === selectedId;
      node.setAttribute('aria-pressed', String(active));
      node.setAttribute('tabindex', p.id === tabStopId ? '0' : '-1');
      if (active && focus) node.focus({preventScroll: true});
    });
    if (changed || !inspection.children.length) updateInspection(point);
  }
  function clearPointerSelection() {
    const focused = pointNodes.find(({node}) => node === document.activeElement && node.matches(':focus-visible'));
    selectPoint(focused?.point ?? null);
  }
  function renderChart() {
    if (!visible.length) {
      chart.replaceChildren();
      pointNodes = [];
      geometry = null;
      selectPoint(null);
      return;
    }
    const focusedId = pointNodes.find(({node}) => node === document.activeElement && node.matches(':focus-visible'))?.point.id;
    selectedId = focusedId ?? null;
    updateInspection(visible.find(point => point.id === selectedId));
    const width = Math.max(chart.clientWidth, 250);
    const height = chart.clientHeight || 430;
    const mobile = width < 500;
    const margin = {left: mobile ? 48 : 67, right: 18, top: 41, bottom: 60};
    const plotWidth = width - margin.left - margin.right;
    const plotHeight = height - margin.top - margin.bottom;
    const sx = value => margin.left + (value - xDomain[0]) / (xDomain[1] - xDomain[0]) * plotWidth;
    const sy = value => margin.top + (yDomain[1] - value) / (yDomain[1] - yDomain[0]) * plotHeight;
    geometry = {sx, sy, width, height};
    const svg = svgNode('svg', {viewBox: `0 0 ${width} ${height}`, role: 'group', 'aria-label': `Novelty and test-performance gains for ${visible.length} selected configurations`, 'aria-describedby': 'ns-keyboard-help'});
    const defs = svgNode('defs');
    const clip = svgNode('clipPath', {id: 'ns-plot-clip'});
    clip.append(svgNode('rect', {x: margin.left, y: margin.top, width: plotWidth, height: plotHeight}));
    defs.append(clip); svg.append(defs);
    const axes = svgNode('g', {'aria-hidden': 'true'});
    axes.append(svgNode('text', {x: margin.left, y: 20, class: 'ns-axis-label'}, mobile ? 'Test gain (%)' : 'Relative test-performance gain (%)'));
    [-20, 0, 20, 40, 60, 80, 100].forEach(value => {
      axes.append(svgNode('line', {x1: margin.left, x2: width - margin.right, y1: sy(value), y2: sy(value), class: value === 0 ? 'ns-zero' : 'ns-grid', 'vector-effect': 'non-scaling-stroke'}));
      axes.append(svgNode('text', {x: margin.left - 11, y: sy(value) + 5, 'text-anchor': 'end'}, String(value).replace('-', '−')));
    });
    [1.5, 2, 2.5, 3, 3.5].forEach(value => {
      axes.append(svgNode('line', {x1: sx(value), x2: sx(value), y1: height - margin.bottom, y2: height - margin.bottom + 6, class: 'ns-axis'}));
      axes.append(svgNode('text', {x: sx(value), y: height - margin.bottom + 27, 'text-anchor': 'middle'}, value.toFixed(1)));
    });
    axes.append(svgNode('line', {x1: margin.left, x2: width - margin.right, y1: height - margin.bottom, y2: height - margin.bottom, class: 'ns-axis'}));
    axes.append(svgNode('text', {x: margin.left + plotWidth / 2, y: height - 9, 'text-anchor': 'middle', class: 'ns-axis-label'}, 'Mean novelty (0–4)'));
    svg.append(axes);
    const stats = statistics(visible);
    const plot = svgNode('g', {'clip-path': 'url(#ns-plot-clip)'});
    if (stats) {
      const fitLow = Math.min(...visible.map(point => point.novelty));
      const fitHigh = Math.max(...visible.map(point => point.novelty));
      plot.append(svgNode('line', {x1: sx(fitLow), x2: sx(fitHigh), y1: sy(stats.slope * fitLow + stats.intercept), y2: sy(stats.slope * fitHigh + stats.intercept), class: 'ns-fit', 'aria-hidden': 'true', 'vector-effect': 'non-scaling-stroke'}));
      // Keep the fit key separate from data coordinates and out of the dense point region.
      const legend = svgNode('g', {'aria-hidden': 'true'});
      const lx = width - margin.right - (mobile ? 105 : 118);
      legend.append(svgNode('line', {x1: lx, x2: lx + 22, y1: 20, y2: 20, class: 'ns-fit-key'}));
      legend.append(svgNode('text', {x: lx + 30, y: 25}, 'Linear fit'));
      if (!mobile || width >= 300) svg.append(legend);
    }
    const pointLayer = svgNode('g');
    pointNodes = [];
    visible.forEach((point, index) => {
      const node = svgNode('g', {class: 'ns-point', role: 'button', 'data-point-id': point.id, tabindex: point.id === tabStopId ? '0' : '-1', 'aria-pressed': String(point.id === selectedId), 'aria-label': `${point.task}, ${agentName(point)}. Mean novelty ${number(point.novelty)} out of 4. Relative test-performance gain ${gain(point.gain_percent)}.`, transform: `translate(${sx(point.novelty)}, ${sy(point.gain_percent)})`});
      node.append(svgNode('circle', {r: 11, class: 'ns-ring'}), svgNode('circle', {r: 6.5, class: 'ns-dot'}));
      node.append(svgNode('title', {}, `${point.task} · ${agentName(point)}\nNovelty ${number(point.novelty)} · gain ${gain(point.gain_percent)}`));
      node.addEventListener('focus', () => { tabStopId = point.id; selectPoint(point); });
      node.addEventListener('blur', () => { if (selectedId === point.id) selectPoint(null); });
      node.addEventListener('click', () => selectPoint(point, true));
      node.addEventListener('keydown', event => {
        let next;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % visible.length;
        if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index - 1 + visible.length) % visible.length;
        if (event.key === 'Home') next = 0;
        if (event.key === 'End') next = visible.length - 1;
        if (next !== undefined) { event.preventDefault(); selectPoint(visible[next], true); }
        if (event.key === 'Enter' || event.key === ' ') { event.preventDefault(); selectPoint(point); }
      });
      pointLayer.append(node); pointNodes.push({point, node});
    });
    svg.append(plot, pointLayer);
    chart.replaceChildren(svg);
    if (focusedId && pointNodes.some(p => p.point.id === focusedId)) selectPoint(visible.find(p => p.id === focusedId), true);
  }
  function update() {
    visible = points.filter(p => (taskSelect.value === 'all' || p.task === taskSelect.value) && (agentSelect.value === 'all' || agentName(p) === agentSelect.value)).sort((a, b) => a.novelty - b.novelty || a.gain_percent - b.gain_percent || a.id.localeCompare(b.id));
    selectedId = null;
    if (!visible.some(point => point.id === tabStopId)) tabStopId = visible[0]?.id ?? null;
    const stats = statistics(visible);
    const allSelected = taskSelect.value === 'all' && agentSelect.value === 'all';
    const heading = document.getElementById('novelty-title');
    heading.replaceChildren(document.createTextNode('Novelty and performance'), document.createElement('br'), document.createTextNode(allSelected ? ' move together.' : ' in this selection.'));
    $('[data-ns-r]').textContent = stats ? stats.r.toFixed(2).replace('-', '−') : '—';
    $('[data-ns-count]').textContent = visible.length === points.length ? `All ${visible.length} configurations` : `${visible.length} selected ${visible.length === 1 ? 'configuration' : 'configurations'}`;
    renderChart();
    updateInspection(visible.find(point => point.id === selectedId));
  }
  function closestPoint(event, radius = 10) {
    if (!geometry || !visible.length) return null;
    const bounds = chart.getBoundingClientRect();
    const px = (event.clientX - bounds.left) * geometry.width / bounds.width;
    const py = (event.clientY - bounds.top) * geometry.height / bounds.height;
    let result = null, distance = radius * radius;
    visible.forEach(point => {
      const d = (geometry.sx(point.novelty) - px) ** 2 + (geometry.sy(point.gain_percent) - py) ** 2;
      if (d < distance) { result = point; distance = d; }
    });
    return result;
  }
  chart.addEventListener('pointermove', event => {
    if (event.pointerType === 'touch') return;
    const point = closestPoint(event);
    if (point) selectPoint(point);
    else clearPointerSelection();
  });
  chart.addEventListener('pointerleave', event => {
    if (event.pointerType !== 'touch') clearPointerSelection();
  });
  chart.addEventListener('pointercancel', clearPointerSelection);
  chart.addEventListener('click', event => {
    if (event.target.closest('.ns-point')) return;
    const point = closestPoint(event, event.pointerType === 'touch' ? 22 : 10);
    if (point) selectPoint(point, true);
    else selectPoint(null);
  });
  root.addEventListener('click', event => {
    if (!chart.contains(event.target)) selectPoint(null);
  });
  taskSelect.addEventListener('change', update);
  agentSelect.addEventListener('change', update);
  $('[data-ns-reset]').addEventListener('click', () => { taskSelect.value = 'all'; agentSelect.value = 'all'; update(); });

  fetch('assets/data/novelty.json').then(response => {
    if (!response.ok) throw new Error('Chart data unavailable');
    return response.json();
  }).then(data => {
    if (!Array.isArray(data.points) || data.points.length !== 42 || data.points.some(p => !p.id || !p.task || !p.harness || !p.model || !Number.isFinite(p.novelty) || !Number.isFinite(p.gain_percent) || p.novelty < xDomain[0] || p.novelty > xDomain[1] || p.gain_percent < yDomain[0] || p.gain_percent > yDomain[1])) throw new Error('Chart data invalid');
    points = data.points;
    taskOrder.filter(task => points.some(p => p.task === task)).forEach(task => taskSelect.add(new Option(task, task)));
    [...new Set(points.map(agentName))].forEach(agent => agentSelect.add(new Option(agent, agent)));
    $('[data-ns-body]').hidden = false;
    $('[data-ns-loading]').hidden = true;
    update();
    if ('ResizeObserver' in window) {
      new ResizeObserver(() => { cancelAnimationFrame(resizeFrame); resizeFrame = requestAnimationFrame(renderChart); }).observe(chart);
    } else window.addEventListener('resize', renderChart);
    root.classList.add('is-ready');
  }).catch(() => {
    $('[data-ns-loading]').hidden = true;
    $('[data-ns-body]').hidden = true;
    $('[data-ns-fallback]').hidden = false;
  });
})();
