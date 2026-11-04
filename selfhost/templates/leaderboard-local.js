/* Same-origin self-hosted leaderboard. The release builder installs this asset. */
(() => {
  'use strict';
  const root = document.getElementById('leaderboard');
  if (!root) return;
  const container = root.querySelector('[data-lb-embed]');
  const status = root.querySelector('[data-lb-load-status]');
  if (!container || !status) return;
  container.dataset.state = 'loading';
  const unavailable = () => {
    container.dataset.state = 'error';
    status.hidden = false;
    status.textContent = 'Leaderboard unavailable. Please try again later.';
  };
  const heroLink = document.querySelector('.huggingface-button');
  if (heroLink) {
    heroLink.href = '/leaderboard/';
    heroLink.textContent = 'Leaderboard';
    heroLink.removeAttribute('aria-disabled');
    heroLink.removeAttribute('role');
    heroLink.title = 'AutoRSE leaderboard';
  }
  const frame = document.createElement('iframe');
  frame.className = 'lb-frame';
  frame.title = 'AutoRSE leaderboard';
  frame.loading = 'lazy';
  frame.referrerPolicy = 'same-origin';
  frame.src = '/leaderboard/?embed=1';
  frame.setAttribute('aria-hidden', 'true');
  frame.tabIndex = -1;
  let ready = false, deadline = null;
  const startDeadline = () => {
    if (!ready && deadline === null) deadline = setTimeout(unavailable, 15000);
  };
  frame.addEventListener('error', () => { if (!ready) unavailable(); });
  window.addEventListener('message', event => {
    if (event.origin !== window.location.origin || event.source !== frame.contentWindow ||
        !event.data || event.data.type !== 'autorse-leaderboard-height') return;
    const height = event.data.height;
    if (typeof height === 'number' && Number.isFinite(height) && height >= 120 && height <= 20000) {
      ready = true;
      clearTimeout(deadline);
      container.dataset.state = 'ready';
      status.hidden = true;
      frame.removeAttribute('aria-hidden');
      frame.removeAttribute('tabindex');
      frame.style.height = Math.ceil(height) + 'px';
    }
  });
  container.append(frame);
  if ('IntersectionObserver' in window) {
    const observer = new IntersectionObserver(entries => {
      if (entries.some(entry => entry.isIntersecting)) {
        startDeadline();
        observer.disconnect();
      }
    });
    observer.observe(container);
  } else startDeadline();
})();
