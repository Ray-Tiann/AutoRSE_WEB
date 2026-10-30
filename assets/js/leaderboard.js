/* A future Hugging Face Space is the source of community leaderboard results.
   Empty URLs intentionally keep the coming-soon state; paper results stay separate. */
(() => {
  'use strict';
  const root = document.getElementById('leaderboard');
  if (!root) return;

  function spaceURLs(config) {
    if (!config || !config.spaceUrl || !config.embedUrl) return null;
    const space = new URL(config.spaceUrl);
    const embed = new URL(config.embedUrl);
    const credentialFree = url => !url.username && !url.password && !url.port;
    if (space.protocol !== 'https:' || space.hostname !== 'huggingface.co' ||
        !/^\/spaces\/[^/?#]+\/[^/?#]+\/?$/.test(space.pathname) || !credentialFree(space)) return null;
    if (embed.protocol !== 'https:' || !/^[a-z0-9-]+\.hf\.space$/.test(embed.hostname) ||
        !credentialFree(embed)) return null;
    return {space:space.href, embed:embed.href};
  }

  fetch(new URL('assets/data/leaderboard.json', document.baseURI), {cache:'no-cache'})
    .then(response => response.ok ? response.json() : null)
    .then(config => {
      const urls = spaceURLs(config);
      if (!urls) return;
      const frame = document.createElement('iframe');
      frame.className = 'lb-frame';
      frame.title = 'AutoRSE community leaderboard on Hugging Face';
      frame.loading = 'lazy';
      frame.referrerPolicy = 'strict-origin-when-cross-origin';
      frame.src = urls.embed;
      const link = root.querySelector('[data-lb-space-link]');
      link.href = urls.space;
      root.querySelector('[data-lb-embed]').append(frame);
      root.querySelector('[data-lb-placeholder]').hidden = true;
      root.querySelector('[data-lb-connected]').hidden = false;
      const heroLink = document.querySelector('.huggingface-button');
      if (heroLink) {
        heroLink.href = urls.space;
        heroLink.target = '_blank';
        heroLink.rel = 'noopener noreferrer';
        heroLink.removeAttribute('aria-disabled');
        heroLink.removeAttribute('role');
        heroLink.title = 'AutoRSE community leaderboard on Hugging Face';
      }
    })
    .catch(() => { /* Retain the reserved state if configuration is unavailable. */ });
})();
