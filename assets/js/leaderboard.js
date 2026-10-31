/* Live leaderboard body; the page owns the single submission action. */
(() => {
  'use strict';
  const root = document.getElementById('leaderboard');
  if (!root) return;
  const container = root.querySelector('[data-lb-embed]');
  const status = root.querySelector('[data-lb-load-status]');
  container.dataset.state = 'loading';

  function unavailable() {
    container.dataset.state = 'error';
    status.hidden = false;
    status.textContent = 'Leaderboard unavailable. Please try again later.';
  }

  function spaceURLs(config) {
    if (!config || !config.spaceUrl || !config.embedUrl) return null;
    try {
      const space = new URL(config.spaceUrl), embed = new URL(config.embedUrl);
      const credentialFree = url => !url.username && !url.password && !url.port;
      if (space.protocol !== 'https:' || space.hostname !== 'huggingface.co' ||
          !/^\/spaces\/[^/?#]+\/[^/?#]+\/?$/.test(space.pathname) || !credentialFree(space)) return null;
      if (embed.protocol !== 'https:' || !/^[a-z0-9-]+(?:\.static)?\.hf\.space$/.test(embed.hostname) ||
          !credentialFree(embed)) return null;
      return {space:space.href, embed:embed.href};
    } catch { return null; }
  }

  const request = new AbortController();
  const configTimeout = setTimeout(() => request.abort(), 10000);
  fetch(new URL('assets/data/leaderboard.json', document.baseURI), {cache:'no-cache',signal:request.signal})
    .then(response => { if (!response.ok) throw Error(); return response.json(); })
    .then(config => {
      const urls = spaceURLs(config);
      if (!urls) throw Error();
      const heroLink = document.querySelector('.huggingface-button');
      if (heroLink) {
        heroLink.href = urls.space;
        heroLink.target = '_blank';
        heroLink.rel = 'noopener noreferrer';
        heroLink.removeAttribute('aria-disabled');
        heroLink.removeAttribute('role');
        heroLink.title = 'AutoRSE on Hugging Face';
      }
      const frame = document.createElement('iframe');
      frame.className = 'lb-frame';
      frame.title = 'AutoRSE leaderboard';
      frame.loading = 'lazy';
      frame.referrerPolicy = 'strict-origin-when-cross-origin';
      frame.src = urls.embed;
      frame.setAttribute('aria-hidden', 'true');
      frame.tabIndex = -1;
      let ready = false, deadline = null;
      const expectedOrigin = new URL(urls.embed).origin;
      const startDeadline = () => { if (!ready && deadline === null) deadline = setTimeout(unavailable, 15000); };
      frame.addEventListener('error', () => { if (!ready) unavailable(); });
      window.addEventListener('message', event => {
        if (event.origin !== expectedOrigin || event.source !== frame.contentWindow ||
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
          if (entries.some(entry => entry.isIntersecting)) { startDeadline(); observer.disconnect(); }
        });
        observer.observe(container);
      } else startDeadline();
    })
    .catch(unavailable)
    .finally(() => clearTimeout(configTimeout));
})();
