/* Accessible, dependency-free comparison of the three paper settings. */
(() => {
  'use strict';
  const root = document.querySelector('.idea-modes');
  if (!root) return;
  const tabs = [...root.querySelectorAll('[role="tab"]')];
  const panels = [...root.querySelectorAll('[role="tabpanel"]')];
  const reducedMotion = window.matchMedia('(prefers-reduced-motion: reduce)');
  let arrivalTimer;

  function selectTab(tab, moveFocus = false) {
    if (!tabs.includes(tab)) return;
    clearTimeout(arrivalTimer);
    tabs.forEach(item => {
      const selected = item === tab;
      item.setAttribute('aria-selected', String(selected));
      item.tabIndex = selected ? 0 : -1;
    });
    panels.forEach(panel => {
      const selected = panel.id === tab.getAttribute('aria-controls');
      panel.hidden = !selected;
      panel.classList.remove('is-arriving');
      if (selected && !reducedMotion.matches) {
        // A new panel becomes visible in this frame; animate only this change.
        panel.classList.add('is-arriving');
        arrivalTimer = window.setTimeout(() => panel.classList.remove('is-arriving'), 900);
      }
    });
    root.dataset.mode = tab.dataset.ideaMode;
    if (moveFocus) tab.focus();
  }

  tabs.forEach((tab, index) => {
    tab.addEventListener('click', () => selectTab(tab));
    tab.addEventListener('keydown', event => {
      let next;
      if (event.key === 'ArrowRight') next = (index + 1) % tabs.length;
      if (event.key === 'ArrowLeft') next = (index - 1 + tabs.length) % tabs.length;
      if (event.key === 'Home') next = 0;
      if (event.key === 'End') next = tabs.length - 1;
      if (next === undefined) return;
      event.preventDefault();
      selectTab(tabs[next], true);
    });
  });

  // Selection does not advance on a timer: readers control the comparison.
  root.classList.add('is-enhanced');
})();
