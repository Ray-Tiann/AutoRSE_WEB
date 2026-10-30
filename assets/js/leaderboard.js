/* The Space link can be enabled before the app is deployed.
   An empty embed URL keeps the reserved state; paper results stay separate. */
(() => {
  'use strict';
  const root = document.getElementById('leaderboard');
  if (!root) return;

  function spaceURLs(config) {
    if (!config || !config.spaceUrl) return null;
    const space = new URL(config.spaceUrl);
    const credentialFree = url => !url.username && !url.password && !url.port;
    if (space.protocol !== 'https:' || space.hostname !== 'huggingface.co' ||
        !/^\/spaces\/[^/?#]+\/[^/?#]+\/?$/.test(space.pathname) || !credentialFree(space)) return null;
    if (!config.embedUrl) return {space:space.href, embed:null};
    const embed = new URL(config.embedUrl);
    if (embed.protocol !== 'https:' || !/^[a-z0-9-]+\.hf\.space$/.test(embed.hostname) ||
        !credentialFree(embed)) return {space:space.href, embed:null};
    return {space:space.href, embed:embed.href};
  }

  fetch(new URL('assets/data/leaderboard.json', document.baseURI), {cache:'no-cache'})
    .then(response => response.ok ? response.json() : null)
    .then(config => {
      const urls = spaceURLs(config);
      if (!urls) return;
      const reservedLink = root.querySelector('[data-lb-reserved-link]');
      if (reservedLink) {reservedLink.href = urls.space; reservedLink.hidden = false;}
      const heroLink = document.querySelector('.huggingface-button');
      if (heroLink) {
        heroLink.href = urls.space;
        heroLink.target = '_blank';
        heroLink.rel = 'noopener noreferrer';
        heroLink.removeAttribute('aria-disabled');
        heroLink.removeAttribute('role');
        heroLink.title = 'AutoRSE on Hugging Face';
      }
      if (!urls.embed) return;
      const frame = document.createElement('iframe');
      frame.className = 'lb-frame';
      frame.title = 'AutoRSE community leaderboard on Hugging Face';
      frame.loading = 'lazy';
      frame.referrerPolicy = 'strict-origin-when-cross-origin';
      frame.src = urls.embed;
      const expectedOrigin = new URL(urls.embed).origin;
      window.addEventListener('message', event => {
        if (event.origin !== expectedOrigin || event.source !== frame.contentWindow ||
            !event.data || event.data.type !== 'autorse-leaderboard-height') return;
        const height = event.data.height;
        if (typeof height === 'number' && Number.isFinite(height) && height >= 240 && height <= 20000)
          frame.style.height = Math.ceil(height) + 'px';
      });
      const link = root.querySelector('[data-lb-space-link]');
      link.href = urls.space;
      root.querySelector('[data-lb-embed]').append(frame);
      root.querySelector('[data-lb-placeholder]').hidden = true;
      root.querySelector('[data-lb-connected]').hidden = false;
    })
    .catch(() => { /* Retain the reserved state if configuration is unavailable. */ });
})();
