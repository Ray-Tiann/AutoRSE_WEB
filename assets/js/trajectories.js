(function () {
  'use strict';

  const root = document.querySelector('.trajectory-explorer');
  if (!root) return;
  const NS = 'http://www.w3.org/2000/svg';
  const modelControls = root.querySelector('[data-te-models]');
  const agentSelect = root.querySelector('[data-te-agent]');
  const viewSelect = root.querySelector('[data-te-view]');
  const chart = root.querySelector('[data-te-chart]');
  const title = root.querySelector('[data-te-title]');
  const subtitle = root.querySelector('[data-te-subtitle]');
  const baselineLabel = root.querySelector('[data-te-baseline]');
  const slider = root.querySelector('[data-te-time]');
  const timeLabel = root.querySelector('[data-te-time-label]');
  const table = root.querySelector('[data-te-values]');
  const coverage = root.querySelector('[data-te-coverage]');
  const status = root.querySelector('[data-te-status]');
  const loading = root.querySelector('[data-te-loading]');
  if (!modelControls || !agentSelect || !viewSelect || !chart || !slider || !table) return;

  let data;
  let task;
  let selectedGroup = 'all';
  let view = 'summary';
  let time = 100;
  let layout;
  let cursorLayer;
  let rowCells = [];
  let baselineMethod;
  let legend;
  let tooltip;
  let tooltipVisible = false;
  let tooltipSide = 'left';
  let resizeFrame = 0;
  let pointerFrame = 0;
  let pendingTime = 100;
  const markerDash = ['', '8 4', '2 4'];
  const fmt = value => Number.isFinite(value) ? value.toFixed(5) : 'No observation yet';
  const clamp = (value, low, high) => Math.max(low, Math.min(high, value));

  function node(tag, attrs, content) {
    const element = document.createElementNS(NS, tag);
    Object.entries(attrs || {}).forEach(([key, value]) => element.setAttribute(key, String(value)));
    if (content !== undefined) element.textContent = content;
    return element;
  }

  function html(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
  }

  function marker(shape, x, y, color, size, filled) {
    const attrs = {fill: filled ? color : '#fff', stroke: color, 'stroke-width': filled ? 1.3 : 2.3};
    if (shape === 'square') return node('rect', Object.assign(attrs, {x: x - size, y: y - size, width: size * 2, height: size * 2, rx: .5}));
    if (shape === 'triangle') return node('path', Object.assign(attrs, {d: 'M' + x + ' ' + (y - size * 1.2) + 'L' + (x + size * 1.1) + ' ' + (y + size) + 'L' + (x - size * 1.1) + ' ' + (y + size) + 'Z'}));
    return node('circle', Object.assign(attrs, {cx: x, cy: y, r: size}));
  }

  function groupIcon(group) {
    const icon = node('svg', {viewBox: '0 0 34 18', width: 34, height: 18, 'aria-hidden': 'true'});
    icon.append(node('line', {x1: 1, x2: 33, y1: 9, y2: 9, stroke: group.color, 'stroke-width': 2.7}));
    icon.append(marker(group.marker, 17, 9, group.color, 4, true));
    return icon;
  }

  function selectedSeries() {
    return task.series.filter(series => selectedGroup === 'all' || series.groupId === selectedGroup);
  }

  // Binary search preserves the last known value, including duplicate timestamps.
  function at(rows, x) {
    let low = 0;
    let high = rows.length - 1;
    let found = -1;
    while (low <= high) {
      const middle = (low + high) >> 1;
      if (rows[middle][0] <= x + 1e-9) { found = middle; low = middle + 1; }
      else high = middle - 1;
    }
    return found < 0 ? null : rows[found];
  }

  // Steps are carried forward after an observation; missing starts and gaps remain empty.
  function stepPath(rows, valueIndex) {
    let path = '';
    let active = false;
    let lastValue;
    rows.forEach(row => {
      const x = layout.x(row[0]);
      const value = row[valueIndex];
      if (!Number.isFinite(value)) {
        if (active) path += 'H' + x;
        active = false;
        return;
      }
      const y = layout.y(value);
      if (!active) path += 'M' + x + ' ' + y;
      else if (value !== lastValue) path += 'H' + x + 'V' + y;
      active = true;
      lastValue = value;
    });
    if (active) path += 'H' + layout.x(100);
    return path;
  }

  function bandPath(rows) {
    let segments = [];
    let segment = [];
    rows.forEach(row => {
      if (Number.isFinite(row[2]) && Number.isFinite(row[3])) segment.push(row);
      else if (segment.length) {
        segment.push([row[0], null, segment[segment.length - 1][2], segment[segment.length - 1][3]]);
        segments.push(segment);
        segment = [];
      }
    });
    if (segment.length) {
      const last = segment[segment.length - 1];
      if (last[0] < 100) segment.push([100, null, last[2], last[3]]);
      segments.push(segment);
    }
    return segments.map(points => {
      let path = 'M' + layout.x(points[0][0]) + ' ' + layout.y(points[0][3]);
      for (let i = 1; i < points.length; i++) path += 'H' + layout.x(points[i][0]) + 'V' + layout.y(points[i][3]);
      path += 'L' + layout.x(points[points.length - 1][0]) + ' ' + layout.y(points[points.length - 1][2]);
      for (let i = points.length - 2; i >= 0; i--) path += 'V' + layout.y(points[i][2]) + 'H' + layout.x(points[i][0]);
      return path + 'Z';
    }).join('');
  }

  function niceStep(span) {
    const raw = span / 5;
    const magnitude = Math.pow(10, Math.floor(Math.log10(raw || .01)));
    const normalized = raw / magnitude;
    const unit = [1, 2, 2.5, 5, 10].find(value => value >= normalized) || 10;
    return unit * magnitude;
  }

  // Domain always includes every run for this task, independent of the agent filter or view.
  function domain() {
    let min = task.baseline;
    let max = task.baseline;
    task.series.forEach(series => {
      series.summary.forEach(row => {
        if (Number.isFinite(row[2])) min = Math.min(min, row[2]);
        if (Number.isFinite(row[3])) max = Math.max(max, row[3]);
      });
      series.runs.forEach(run => run.points.forEach(point => {
        if (Number.isFinite(point[1])) {
          min = Math.min(min, point[1]);
          max = Math.max(max, point[1]);
        }
      }));
    });
    const padding = Math.max((max - min) * .055, .001);
    const step = niceStep(max - min + padding * 2);
    const low = Math.max(0, Math.floor((min - padding) / step) * step);
    const high = Math.min(1, Math.ceil((max + padding) / step) * step);
    return {low, high: Math.max(low + step, high), step};
  }

  function renderChart() {
    if (!task) return;
    const width = Math.max(240, Math.floor(chart.clientWidth));
    const compact = width < 600;
    const height = compact ? 340 : 408;
    const margin = {top: 22, right: compact ? 14 : 24, bottom: 62, left: compact ? 62 : 76};
    const limits = domain();
    const innerWidth = width - margin.left - margin.right;
    const innerHeight = height - margin.top - margin.bottom;
    layout = {
      width, height, margin, innerWidth, innerHeight,
      x: x => margin.left + innerWidth * x / 100,
      y: y => margin.top + innerHeight * (limits.high - y) / (limits.high - limits.low)
    };
    const svg = node('svg', {width, height, viewBox: '0 0 ' + width + ' ' + height, role: 'img', 'aria-labelledby': 'te-svg-title te-svg-description'});
    svg.append(node('title', {id: 'te-svg-title'}, task.name + ' validation trajectories'));
    svg.append(node('desc', {id: 'te-svg-description'}, 'Step curves show best-so-far validation scores. ' + (view === 'summary' ? 'Solid curves are available-run medians; shaded bands are the minimum and maximum.' : 'Each line is an individual trial. Solid, dashed, and dotted lines identify trials 1, 2, and 3.') + ' The dashed gray reference is the validation baseline. Use the time slider to inspect values; expand Data & downloads for the accessible numeric table. Missing starts are left empty.'));
    const defs = node('defs');
    const clip = node('clipPath', {id: 'te-plot-clip'});
    clip.append(node('rect', {x: margin.left - 5, y: margin.top - 5, width: innerWidth + 10, height: innerHeight + 10}));
    defs.append(clip);
    svg.append(defs);
    const axis = node('g', {class: 'te-svg-axis'});
    let digits = 2;
    while (digits < 6 && Math.abs(limits.step * Math.pow(10, digits) - Math.round(limits.step * Math.pow(10, digits))) > 1e-7) digits += 1;
    for (let value = limits.low, count = 0; value <= limits.high + limits.step / 10 && count < 12; value += limits.step, count++) {
      const y = layout.y(value);
      axis.append(node('line', {x1: margin.left, x2: width - margin.right, y1: y, y2: y, class: 'te-grid-line'}));
      axis.append(node('text', {x: margin.left - 12, y: y + 5, 'text-anchor': 'end'}, value.toFixed(digits)));
    }
    const ticks = compact ? [0, 25, 50, 75, 100] : [0, 20, 40, 60, 80, 100];
    ticks.forEach(value => {
      const x = layout.x(value);
      axis.append(node('line', {x1: x, x2: x, y1: height - margin.bottom, y2: height - margin.bottom + 6, class: 'te-axis-line'}));
      axis.append(node('text', {x, y: height - margin.bottom + 26, 'text-anchor': 'middle'}, value + '%'));
    });
    axis.append(node('line', {x1: margin.left, x2: width - margin.right, y1: height - margin.bottom, y2: height - margin.bottom, class: 'te-axis-line'}));
    axis.append(node('text', {x: margin.left + innerWidth / 2, y: height - 8, 'text-anchor': 'middle', class: 'te-axis-label'}, compact ? 'Recorded elapsed time (%)' : data.methodology.xAxis));
    svg.append(axis);
    const plot = node('g', {'clip-path': 'url(#te-plot-clip)'});
    const selected = selectedSeries();
    if (view === 'summary') selected.forEach(series => {
      const group = data.groups.find(item => item.id === series.groupId);
      plot.append(node('path', {d: bandPath(series.summary), fill: group.color, 'fill-opacity': .12, stroke: 'none'}));
    });
    plot.append(node('line', {x1: layout.x(0), x2: layout.x(100), y1: layout.y(task.baseline), y2: layout.y(task.baseline), stroke: '#626e80', 'stroke-width': 1.8, 'stroke-dasharray': '6 5'}));
    selected.forEach(series => {
      const group = data.groups.find(item => item.id === series.groupId);
      const rows = view === 'summary' ? [series.summary] : series.runs.map(run => run.points);
      rows.forEach((points, index) => {
        plot.append(node('path', {d: stepPath(points, 1), fill: 'none', stroke: group.color, 'stroke-width': view === 'summary' ? 3 : 2.2, 'stroke-linejoin': 'round', 'stroke-linecap': 'round', 'stroke-dasharray': view === 'summary' ? '' : markerDash[index % markerDash.length], opacity: view === 'summary' ? 1 : .87}));
        // Shape encodes agent identity. Mark only source knots, never a synthetic endpoint.
        let previousX = -Infinity;
        let previousValue = null;
        points.forEach(point => {
          if (!Number.isFinite(point[1]) || point[0] >= 100) return;
          const x = layout.x(point[0]);
          if (point[1] !== previousValue && x - previousX >= (compact ? 66 : 100)) {
            plot.append(marker(group.marker, x, layout.y(point[1]), group.color, view === 'summary' ? 3.6 : 2.6, true));
            previousX = x;
            previousValue = point[1];
          }
        });
      });
    });
    cursorLayer = node('g', {class: 'te-cursor-layer'});
    plot.append(cursorLayer);
    svg.append(plot);
    chart.replaceChildren(svg);
    if (tooltip) chart.append(tooltip);
    updateCursor();
  }


  function renderLegend() {
    if (!legend) return;
    legend.replaceChildren();
    selectedSeries().forEach(series => {
      const group = data.groups.find(item => item.id === series.groupId);
      const item = html('span', 'te-legend-item');
      item.setAttribute('role', 'listitem');
      item.append(groupIcon(group), html('span', '', group.label));
      legend.append(item);
    });
  }

  function updateTooltip() {
    if (!tooltip) return;
    tooltip.hidden = !tooltipVisible;
    tooltip.classList.toggle('te-tooltip-right', tooltipSide === 'right');
    if (!tooltipVisible) return;
    const displayTime = Math.abs(time - Math.round(time)) < .05 ? String(Math.round(time)) : time.toFixed(1);
    tooltip.replaceChildren(html('strong', 'te-tooltip-time', displayTime + '% recorded time'));
    selectedSeries().forEach(series => {
      const group = data.groups.find(item => item.id === series.groupId);
      const item = html('div', 'te-tooltip-item');
      const heading = html('span', 'te-tooltip-name');
      heading.append(groupIcon(group), html('span', '', group.model));
      item.append(heading);
      if (view === 'summary') {
        const row = at(series.summary, time);
        const value = html('strong', 'te-tooltip-score', row ? fmt(row[1]) : 'No observation yet');
        item.append(value);
      } else {
        const values = html('span', 'te-tooltip-trials');
        series.runs.forEach((run, index) => {
          const point = at(run.points, time);
          const value = html('span');
          value.append(html('span', '', 'T' + (index + 1) + ' '), html('strong', '', point ? fmt(point[1]) : 'No observation yet'));
          values.append(value);
        });
        item.append(values);
      }
      tooltip.append(item);
    });
  }

  function renderTable() {
    rowCells = [];
    const caption = html('caption', 'te-table-caption', 'Validation scores at the selected time');
    const head = html('thead');
    const headRow = html('tr');
    ['Agent configuration', view === 'summary' ? 'Median · min–max' : 'Individual trial scores', 'Available trials'].forEach(label => {
      const cell = html('th', '', label);
      cell.scope = 'col';
      headRow.append(cell);
    });
    head.append(headRow);
    const body = html('tbody');
    selectedSeries().forEach(series => {
      const group = data.groups.find(item => item.id === series.groupId);
      const row = html('tr');
      const nameCell = html('th', 'te-agent-name');
      nameCell.scope = 'row';
      const identity = html('span', 'te-agent-identity');
      const label = html('span');
      label.append(html('strong', '', group.model), html('span', 'te-harness', group.harness));
      identity.append(groupIcon(group), label);
      nameCell.append(identity);
      const value = html('td', 'te-values-cell');
      const count = html('td', 'te-count-cell');
      row.append(nameCell, value, count);
      body.append(row);
      rowCells.push({series, value, count});
    });
    table.replaceChildren(caption, head, body);
  }

  function updateReadout() {
    const displayTime = Math.abs(time - Math.round(time)) < .05 ? String(Math.round(time)) : time.toFixed(1);
    if (timeLabel) timeLabel.textContent = displayTime + '%';
    slider.value = String(time);
    slider.setAttribute('aria-valuetext', displayTime + '% of normalized recorded elapsed time');
    const caption = table.querySelector('caption');
    if (caption) caption.textContent = 'Validation at ' + displayTime + '% of recorded time';
    rowCells.forEach(({series, value, count}) => {
      const row = at(series.summary, time);
      if (view === 'summary') {
        const median = html('strong', 'te-value-main', row ? fmt(row[1]) : 'No observation yet');
        value.replaceChildren(median);
        if (row && Number.isFinite(row[1])) value.append(html('span', 'te-value-range', fmt(row[2]) + ' – ' + fmt(row[3])));
      } else {
        const list = html('span', 'te-trial-values');
        series.runs.forEach((run, index) => {
          const point = at(run.points, time);
          const item = html('span', 'te-trial-value');
          item.append(html('span', 'te-trial-key', 'T' + (index + 1)), html('strong', '', point ? fmt(point[1]) : 'No observation yet'));
          item.title = 'Trial ' + (index + 1) + ': ' + run.id;
          list.append(item);
        });
        value.replaceChildren(list);
      }
      count.textContent = (row ? row[4] : 0) + ' / ' + series.totalRuns;
      count.setAttribute('aria-label', (row ? row[4] : 0) + ' of ' + series.totalRuns + ' trials have an observation at this time');
    });
  }

  function updateCursor() {
    if (!cursorLayer || !layout) return;
    const x = layout.x(time);
    cursorLayer.replaceChildren(node('line', {x1: x, x2: x, y1: layout.margin.top, y2: layout.height - layout.margin.bottom, stroke: '#293e5e', 'stroke-width': 1.3, 'stroke-dasharray': '3 4', opacity: .65}));
    selectedSeries().forEach(series => {
      const group = data.groups.find(item => item.id === series.groupId);
      if (view === 'summary') {
        const value = at(series.summary, time);
        if (value && Number.isFinite(value[1])) cursorLayer.append(marker(group.marker, x, layout.y(value[1]), group.color, 5.2, false));
      } else series.runs.forEach(run => {
        const point = at(run.points, time);
        if (point && Number.isFinite(point[1])) cursorLayer.append(marker(group.marker, x, layout.y(point[1]), group.color, 4, false));
      });
    });
    updateReadout();
    updateTooltip();
  }

  function setTime(value) {
    time = clamp(Number(value) || 0, 0, 100);
    updateCursor();
  }

  function refresh(announce) {
    title.textContent = task.name;
    subtitle.textContent = task.metric + ' · best-so-far validation';
    baselineLabel.textContent = 'Validation baseline ' + fmt(task.baseline);
    if (baselineMethod) baselineMethod.textContent = task.name + ' baseline scope: ' + task.baselineScope + '. ' + task.baselineProvenance;
    modelControls.querySelectorAll('button').forEach(button => button.setAttribute('aria-pressed', String(button.dataset.teTask === task.id)));
    renderLegend();
    renderTable();
    renderChart();
    const runs = selectedSeries().reduce((sum, series) => sum + series.totalRuns, 0);
    coverage.textContent = view === 'summary'
      ? 'Median and min–max across available trials. ' + runs + ' included trials for this selection.'
      : 'One line per trial: T1 solid · T2 dashed · T3 dotted. ' + runs + ' included trials.';
    if (task.id === 'intsr' && (selectedGroup === 'all' || selectedGroup === 'gpt')) coverage.textContent += ' IntSR × Codex has 2 trials; one source-audited run is excluded.';
    if (announce && status) status.textContent = task.name + '. ' + (selectedGroup === 'all' ? 'All three agent configurations.' : data.groups.find(group => group.id === selectedGroup).label + '.') + ' ' + (view === 'summary' ? 'Median and min–max view.' : 'Individual trials view.');
  }

  function pointerTime(event) {
    if (!layout) return;
    const bounds = chart.getBoundingClientRect();
    const x = event.clientX - bounds.left;
    if (x < layout.margin.left - 8 || x > layout.width - layout.margin.right + 8) return;
    tooltipVisible = true;
    tooltipSide = x > layout.width / 2 ? 'left' : 'right';
    pendingTime = clamp((x - layout.margin.left) / layout.innerWidth * 100, 0, 100);
    if (!pointerFrame) pointerFrame = requestAnimationFrame(() => { pointerFrame = 0; setTime(pendingTime); });
  }

  fetch(root.dataset.src || 'assets/data/trajectories.json', {credentials: 'same-origin'})
    .then(response => { if (!response.ok) throw new Error('Data request failed'); return response.json(); })
    .then(source => {
      if (!source.tasks || !source.tasks.length || !source.groups || !source.groups.length) throw new Error('Incomplete trajectory data');
      data = source;
      task = data.tasks[0];
      legend = html('div', 'te-inline-legend');
      legend.setAttribute('role', 'list');
      legend.setAttribute('aria-label', 'Visible agent configurations');
      const plotHeading = root.querySelector('.te-plot-heading');
      if (plotHeading) plotHeading.insertAdjacentElement('afterend', legend);
      tooltip = html('div', 'te-tooltip');
      tooltip.setAttribute('aria-hidden', 'true');
      tooltip.hidden = true;
      const methods = root.querySelector('.te-method-body');
      if (methods) { baselineMethod = html('p'); methods.append(baselineMethod); }
      modelControls.replaceChildren();
      data.tasks.forEach(item => {
        const button = html('button', 'te-model-button', item.name);
        button.type = 'button';
        button.dataset.teTask = item.id;
        button.setAttribute('aria-pressed', String(item.id === task.id));
        button.addEventListener('click', () => { task = item; refresh(true); });
        modelControls.append(button);
      });
      modelControls.addEventListener('keydown', event => {
        const buttons = Array.from(modelControls.querySelectorAll('button'));
        const index = buttons.indexOf(document.activeElement);
        if (index < 0) return;
        let next = index;
        if (event.key === 'ArrowRight' || event.key === 'ArrowDown') next = (index + 1) % buttons.length;
        else if (event.key === 'ArrowLeft' || event.key === 'ArrowUp') next = (index + buttons.length - 1) % buttons.length;
        else if (event.key === 'Home') next = 0;
        else if (event.key === 'End') next = buttons.length - 1;
        else return;
        event.preventDefault();
        buttons[next].focus();
        buttons[next].click();
      });
      agentSelect.replaceChildren(new Option('All 3 representative configurations', 'all'));
      data.groups.forEach(group => agentSelect.append(new Option(group.label, group.id)));
      agentSelect.disabled = false;
      viewSelect.disabled = false;
      slider.disabled = false;
      agentSelect.addEventListener('change', () => { selectedGroup = agentSelect.value; refresh(true); });
      viewSelect.addEventListener('change', () => { view = viewSelect.value; refresh(true); });
      slider.addEventListener('input', () => {
        tooltipVisible = true;
        tooltipSide = Number(slider.value) > 50 ? 'left' : 'right';
        setTime(slider.value);
      });
      chart.addEventListener('pointermove', event => { if (event.pointerType === 'mouse' || event.buttons) pointerTime(event); });
      chart.addEventListener('pointerleave', event => {
        if (event.pointerType === 'mouse') { tooltipVisible = false; updateTooltip(); }
      });
      chart.addEventListener('pointerdown', event => {
        pointerTime(event);
        if (event.pointerType !== 'mouse') chart.setPointerCapture(event.pointerId);
      });
      if (loading) loading.hidden = true;
      root.classList.add('is-ready');
      refresh(false);
      const resize = () => {
        cancelAnimationFrame(resizeFrame);
        resizeFrame = requestAnimationFrame(renderChart);
      };
      if ('ResizeObserver' in window) new ResizeObserver(resize).observe(chart);
      else window.addEventListener('resize', resize);
    })
    .catch(error => {
      root.classList.add('has-error');
      if (loading) {
        loading.textContent = 'The interactive data could not load. You can still open the original figure or download the source data below.';
        loading.setAttribute('role', 'status');
      }
      console.warn('AutoRSE trajectory explorer:', error.message);
    });
}());
