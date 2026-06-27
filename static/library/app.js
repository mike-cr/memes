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
            <a class="card-action" href="${meme.editUrl}" aria-label="Edit ${escapeHtml(meme.title)}">
              ${iconSvg('edit')}
            </a>
            <a class="card-action" href="${meme.downloadUrl}" aria-label="Download ${escapeHtml(meme.title)}">
              ${iconSvg('download')}
            </a>
            <button class="card-action" type="button" data-copy-link="${meme.publicUrl}" aria-label="Copy share link for ${escapeHtml(meme.title)}">
              ${iconSvg('link')}
            </button>
            <form method="post" action="${meme.deleteUrl}">
              <input type="hidden" name="csrfmiddlewaretoken" value="${csrfToken()}">
              <button class="card-action danger" type="submit" data-confirm="Delete this meme?" aria-label="Delete ${escapeHtml(meme.title)}">
                ${iconSvg('delete')}
              </button>
            </form>
          </div>
        </div>
      </article>
    `;
  }

  function iconSvg(name) {
    const paths = {
      edit: 'M4 20h4l11-11-4-4L4 16v4zM14 6l4 4',
      download: 'M12 3v12m0 0 5-5m-5 5-5-5M5 21h14',
      link: 'M10 13a5 5 0 0 0 7 0l2-2a5 5 0 0 0-7-7l-1 1M14 11a5 5 0 0 0-7 0l-2 2a5 5 0 0 0 7 7l1-1',
      delete: 'M4 7h16M10 11v6M14 11v6M6 7l1 14h10l1-14M9 7V4h6v3',
    };
    return `<svg viewBox="0 0 24 24" aria-hidden="true"><path d="${paths[name]}"></path></svg>`;
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
    const state = document.querySelector('[data-library-state]');
    const sentinel = document.querySelector('[data-load-sentinel]');
    if (!input || !grid) {
      return;
    }
    let query = input.value;
    let nextPage = state && state.dataset.nextPage ? Number(state.dataset.nextPage) : null;
    let hasNext = state ? state.dataset.hasNext === 'true' : false;
    let loading = false;
    let shown = grid.querySelectorAll('.meme-card').length;
    let total = state && state.dataset.total ? Number(state.dataset.total) : shown;

    function updateCount() {
      if (count) {
        count.textContent = `${shown} of ${total} shown`;
      }
      if (sentinel) {
        sentinel.textContent = hasNext ? 'Loading more...' : '';
        sentinel.hidden = !hasNext;
      }
    }

    async function fetchPage(page, mode) {
      if (loading) {
        return;
      }
      loading = true;
      if (sentinel && hasNext) {
        sentinel.textContent = 'Loading more...';
      }
      const params = new URLSearchParams({ q: query, page: String(page) });
      const response = await fetch('/api/memes/?' + params.toString());
      loading = false;
      if (!response.ok) {
        return;
      }
      const data = await response.json();
      total = data.total;
      hasNext = data.hasNext;
      nextPage = data.nextPage;

      if (mode === 'replace') {
        grid.innerHTML = data.memes.length
          ? data.memes.map(cardHtml).join('')
          : '<div class="empty-state">No matching memes.</div>';
      } else if (data.memes.length) {
        grid.insertAdjacentHTML('beforeend', data.memes.map(cardHtml).join(''));
      }
      shown = grid.querySelectorAll('.meme-card').length;
      updateCount();
    }

    const runSearch = debounce(() => {
      query = input.value;
      hasNext = false;
      nextPage = null;
      fetchPage(1, 'replace');
    }, 180);

    input.addEventListener('input', runSearch);
    document.querySelectorAll('[data-search-token]').forEach((button) => {
      button.addEventListener('click', () => {
        input.value = button.dataset.searchToken;
        runSearch();
      });
    });

    if ('IntersectionObserver' in window && sentinel) {
      const observer = new IntersectionObserver((entries) => {
        if (entries.some((entry) => entry.isIntersecting) && hasNext && nextPage) {
          fetchPage(nextPage, 'append');
        }
      }, { rootMargin: '500px 0px' });
      observer.observe(sentinel);
    } else {
      window.addEventListener('scroll', debounce(() => {
        if (!hasNext || !nextPage || !sentinel) {
          return;
        }
        const bottom = sentinel.getBoundingClientRect().top - window.innerHeight;
        if (bottom < 500) {
          fetchPage(nextPage, 'append');
        }
      }, 120));
    }

    updateCount();
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
        const previousLabel = copyButton.getAttribute('aria-label');
        copyButton.setAttribute('aria-label', 'Copied');
        copyButton.classList.add('copied');
        window.setTimeout(() => {
          copyButton.setAttribute('aria-label', previousLabel);
          copyButton.classList.remove('copied');
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
