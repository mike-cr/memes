(function () {
  function csrfToken() {
    const token = document.querySelector('[name=csrfmiddlewaretoken]');
    return token ? token.value : '';
  }

  function debounce(fn, delay) {
    let timer;
    return function (...args) {
      window.clearTimeout(timer);
      timer = window.setTimeout(() => fn.apply(this, args), delay);
    };
  }

  function initTagWidget(widget) {
    const input = widget.querySelector('[data-tag-input]');
    const value = widget.querySelector('[data-tag-value]');
    const chips = widget.querySelector('[data-tag-chips]');
    const suggestions = widget.querySelector('[data-tag-suggestions]');
    let tags = (widget.dataset.initialTags || value.value || '')
      .split(',')
      .map((tag) => tag.trim().toLowerCase())
      .filter(Boolean);

    function sync() {
      value.value = tags.join(',');
      chips.innerHTML = '';
      tags.forEach((tag) => {
        const chip = document.createElement('button');
        chip.type = 'button';
        chip.textContent = tag + ' x';
        chip.addEventListener('click', () => {
          tags = tags.filter((item) => item !== tag);
          sync();
        });
        chips.appendChild(chip);
      });
    }

    function addTag(raw) {
      const tag = raw.trim().toLowerCase().replace(/\s+/g, ' ');
      if (!tag || tags.includes(tag)) {
        return;
      }
      tags.push(tag);
      input.value = '';
      suggestions.style.display = 'none';
      sync();
    }

    const searchTags = debounce(async () => {
      const query = input.value.trim();
      if (!query) {
        suggestions.style.display = 'none';
        return;
      }
      const response = await fetch('/api/tags/?q=' + encodeURIComponent(query), {
        headers: { 'X-CSRFToken': csrfToken() },
      });
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      suggestions.innerHTML = '';
      data.tags
        .filter((tag) => !tags.includes(tag.name))
        .forEach((tag) => {
          const option = document.createElement('button');
          option.type = 'button';
          option.textContent = tag.name;
          option.addEventListener('click', () => addTag(tag.name));
          suggestions.appendChild(option);
        });
      suggestions.style.display = suggestions.children.length ? 'block' : 'none';
    }, 140);

    input.addEventListener('input', searchTags);
    input.addEventListener('keydown', (event) => {
      if (event.key === 'Enter' || event.key === ',') {
        event.preventDefault();
        addTag(input.value);
      }
      if (event.key === 'Backspace' && !input.value && tags.length) {
        tags.pop();
        sync();
      }
    });
    input.closest('form').addEventListener('submit', () => addTag(input.value));
    sync();
  }

  function cardHtml(meme) {
    const tags = meme.tags.map((tag) => `<span>${escapeHtml(tag)}</span>`).join('');
    return `
      <article class="meme-card">
        <button class="thumb-button" type="button" data-open-image="${meme.publicUrl}" data-download-url="${meme.downloadUrl}" data-title="${escapeHtml(meme.title)}">
          <img src="${meme.thumbnailUrl}" alt="${escapeHtml(meme.title)}">
        </button>
        <div class="meme-meta">
          <h2>${escapeHtml(meme.title)}</h2>
          <div class="tag-list">${tags}</div>
          <div class="card-actions">
            <a href="${meme.editUrl}">Edit</a>
            <a href="${meme.downloadUrl}">Download</a>
            <button type="button" data-copy-link="${meme.publicUrl}">Copy link</button>
            <form method="post" action="${meme.deleteUrl}">
              <input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken()}">
              <button type="submit" data-confirm="Delete this meme?">Delete</button>
            </form>
          </div>
        </div>
      </article>
    `;
  }

  function escapeHtml(value) {
    return String(value).replace(/[&<>"']/g, (char) => ({
      '&': '&amp;',
      '<': '&lt;',
      '>': '&gt;',
      '"': '&quot;',
      "'": '&#39;',
    }[char]));
  }

  function initSearch() {
    const input = document.querySelector('[data-meme-search]');
    const grid = document.querySelector('[data-meme-grid]');
    const count = document.querySelector('[data-result-count]');
    if (!input || !grid) {
      return;
    }

    const runSearch = debounce(async () => {
      const response = await fetch('/api/memes/?q=' + encodeURIComponent(input.value));
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      grid.innerHTML = data.memes.length
        ? data.memes.map(cardHtml).join('')
        : '<div class="empty-state">No matching memes.</div>';
      count.textContent = data.memes.length + ' shown';
    }, 180);

    input.addEventListener('input', runSearch);
    document.querySelectorAll('[data-search-token]').forEach((button) => {
      button.addEventListener('click', () => {
        input.value = button.dataset.searchToken;
        runSearch();
      });
    });
  }

  function initModal() {
    const modal = document.querySelector('[data-image-modal]');
    if (!modal) {
      return;
    }
    const image = modal.querySelector('[data-modal-image]');
    const download = modal.querySelector('[data-modal-download]');
    const copy = modal.querySelector('[data-modal-copy]');
    modal.querySelector('[data-modal-close]').addEventListener('click', () => modal.close());

    document.addEventListener('click', async (event) => {
      const openButton = event.target.closest('[data-open-image]');
      const copyButton = event.target.closest('[data-copy-link]');
      const confirmButton = event.target.closest('[data-confirm]');

      if (openButton) {
        image.src = openButton.dataset.openImage;
        image.alt = openButton.dataset.title || '';
        download.href = openButton.dataset.downloadUrl;
        copy.dataset.copyLink = openButton.dataset.openImage;
        modal.showModal();
      }

      if (copyButton) {
        await navigator.clipboard.writeText(copyButton.dataset.copyLink);
        copyButton.textContent = 'Copied';
        window.setTimeout(() => {
          copyButton.textContent = 'Copy link';
        }, 1200);
      }

      if (confirmButton && !window.confirm(confirmButton.dataset.confirm)) {
        event.preventDefault();
      }
    });
  }

  document.querySelectorAll('[data-tag-widget]').forEach(initTagWidget);
  initSearch();
  initModal();
}());
