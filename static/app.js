const $ = (selector, root = document) => root.querySelector(selector);
const $$ = (selector, root = document) => Array.from(root.querySelectorAll(selector));

const state = {
  currentPage: 'overview',
  resources: [],
  lastQuestion: '',
  lastStudioPayload: null,
  lastDraft: '',
  categoryColors: ['#56c6d2', '#f0a07d', '#9690e8', '#62bb9c', '#81b9d8', '#d7b867']
};

function escapeHtml(value = '') {
  return String(value).replace(/[&<>"']/g, ch => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;'
  }[ch]));
}

function formatSimpleMarkdown(text = '') {
  return escapeHtml(text)
    .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
    .replace(/`([^`]+)`/g, '<code>$1</code>')
    .replace(/\n/g, '<br>');
}

function resourceIcon(type = 'Article') {
  const icons = {
    'Research Paper': '▤', Report: '▧', Dataset: '◫', Article: '≋',
    Image: '▧', Video: '▷', Other: '◈'
  };
  return icons[type] || '◈';
}

function typeClass(type = '') {
  return String(type).toLowerCase().replace(/[^a-z]+/g, '-').replace(/^-|-$/g, '');
}

function toast(message, kind = 'success', title = '') {
  const region = $('#toast-region');
  const node = document.createElement('div');
  node.className = `toast ${kind === 'error' ? 'error' : ''}`;
  node.innerHTML = `${title ? `<strong>${escapeHtml(title)}</strong>` : ''}${escapeHtml(message)}`;
  region.appendChild(node);
  window.setTimeout(() => {
    node.style.opacity = '0';
    node.style.transform = 'translateY(5px)';
    window.setTimeout(() => node.remove(), 220);
  }, 3600);
}

async function requestJson(url, options = {}) {
  const response = await fetch(url, options);
  let payload = {};
  try { payload = await response.json(); } catch (_) { /* non-JSON response */ }
  if (!response.ok) throw new Error(payload.error || `Request failed (${response.status})`);
  return payload;
}

function switchPage(page) {
  if (!['overview', 'library', 'assistant', 'studio'].includes(page)) page = 'overview';
  state.currentPage = page;
  $$('.page-section').forEach(section => section.classList.add('hidden'));
  const target = $(`#page-${page}`);
  if (target) target.classList.remove('hidden');
  $$('.nav-item[data-page]').forEach(item => item.classList.toggle('active', item.dataset.page === page));
  const names = { overview: 'Overview', library: 'Knowledge library', assistant: 'Ask Polar AI', studio: 'Media studio' };
  $('#current-crumb').textContent = names[page];
  $('#sidebar').classList.remove('open');
  if (page === 'library') loadLibrary();
  if (page === 'overview') loadDashboard();
  window.scrollTo({ top: 0, behavior: 'smooth' });
}

function makeResourceRow(resource) {
  const type = escapeHtml(resource.type || 'Article');
  const category = escapeHtml(resource.category || 'General');
  const region = escapeHtml(resource.region || 'Global');
  const year = resource.year ? escapeHtml(resource.year) : '—';
  const title = escapeHtml(resource.title || 'Untitled resource');
  const author = escapeHtml(resource.author || 'Source not specified');
  return `<tr>
    <td><div class="resource-name"><span class="resource-file-icon type-${typeClass(type)}">${resourceIcon(type)}</span><div><strong>${title}</strong><small>${author}</small></div></div></td>
    <td><span class="topic-tag">${category}</span></td>
    <td><span class="region-tag">${region}</span></td>
    <td>${year}</td>
    <td class="row-actions"><button class="row-open" data-open-resource="${Number(resource.id)}">Open ↗</button></td>
  </tr>`;
}

async function loadDashboard() {
  try {
    const data = await requestJson('/api/dashboard');
    $('#stat-resources').textContent = data.total_resources ?? '0';
    $('#stat-views').textContent = data.total_views ?? '0';
    $('#stat-downloads').textContent = data.total_downloads ?? '0';
    $('#stat-topics').textContent = (data.categories || []).length;
    $('#nav-resource-count').textContent = String(data.total_resources || 0).padStart(2, '0');
    $('#recent-resource-rows').innerHTML = (data.recent || []).length
      ? data.recent.map(makeResourceRow).join('')
      : '<tr><td colspan="5" class="table-loading">No resources yet. Add the first one to your library.</td></tr>';
    renderCategoryChart(data.categories || []);
    state.resources = data.recent || [];
  } catch (error) {
    $('#recent-resource-rows').innerHTML = '<tr><td colspan="5" class="table-loading">Dashboard could not connect to the server. Refresh after restarting the app.</td></tr>';
    toast(error.message, 'error', 'Dashboard unavailable');
  }
}

function renderCategoryChart(categories) {
  const list = categories.slice(0, 5);
  const chart = $('#category-chart');
  const legend = $('#category-legend');
  if (!list.length) {
    chart.innerHTML = '<div class="table-loading">Add resources to see topic distribution.</div>';
    legend.innerHTML = '';
    return;
  }
  const max = Math.max(...list.map(item => Number(item.count) || 0), 1);
  chart.innerHTML = list.map((item, index) => {
    const count = Number(item.count) || 0;
    const height = Math.max(12, Math.round((count / max) * 105));
    return `<div class="bar-column"><span class="bar-value">${count}</span><div class="bar" style="height:${height}px"></div><span class="bar-label" title="${escapeHtml(item.category)}">${escapeHtml(item.category)}</span></div>`;
  }).join('');
  legend.innerHTML = list.map((item, index) => `<div class="legend-item"><span class="legend-dot" style="background:${state.categoryColors[index % state.categoryColors.length]}"></span><div class="legend-copy"><span>${escapeHtml(item.category)}</span><strong>${item.count} ${Number(item.count) === 1 ? 'resource' : 'resources'}</strong></div></div>`).join('');
}

async function loadLibrary() {
  const params = new URLSearchParams();
  const query = $('#library-search').value.trim();
  const category = $('#filter-category').value;
  const region = $('#filter-region').value;
  const type = $('#filter-type').value;
  if (query) params.set('q', query);
  if (category) params.set('category', category);
  if (region) params.set('region', region);
  if (type) params.set('type', type);
  const grid = $('#resource-grid');
  grid.innerHTML = '<div class="loading-card">Gathering the polar knowledge…</div>';
  try {
    const data = await requestJson(`/api/resources?${params.toString()}`);
    fillFilterOptions(data.filters || {});
    state.resources = data.items || [];
    $('#library-result-count').textContent = `${data.count} ${data.count === 1 ? 'resource' : 'resources'} found`;
    grid.innerHTML = data.items.length ? data.items.map(makeResourceCard).join('') : '';
    $('#library-empty').classList.toggle('hidden', data.items.length > 0);
    grid.classList.toggle('hidden', data.items.length === 0);
  } catch (error) {
    grid.innerHTML = `<div class="loading-card">${escapeHtml(error.message)}. Check that the local server is running.</div>`;
  }
}

function fillFilterOptions(filters) {
  const definitions = [
    ['filter-category', filters.categories || [], 'All topics'],
    ['filter-region', filters.regions || [], 'All regions'],
    ['filter-type', filters.types || [], 'All types']
  ];
  definitions.forEach(([id, values, label]) => {
    const select = $(`#${id}`);
    const existing = select.value;
    const currentValues = Array.from(select.options).slice(1).map(option => option.value);
    if (JSON.stringify(currentValues) === JSON.stringify(values)) return;
    select.innerHTML = `<option value="">${label}</option>` + values.map(value => `<option value="${escapeHtml(value)}">${escapeHtml(value)}</option>`).join('');
    if (values.includes(existing)) select.value = existing;
  });
}

function makeResourceCard(resource) {
  const tags = String(resource.tags || '').split(',').map(tag => tag.trim()).filter(Boolean).slice(0, 3);
  const type = escapeHtml(resource.type || 'Article');
  return `<article class="resource-card">
    <div class="card-topline"><span class="card-type"><span class="type-mini">${resourceIcon(type)}</span>${type}</span><span class="card-region">${escapeHtml(resource.region || 'Global')}</span></div>
    <h3>${escapeHtml(resource.title)}</h3>
    <p class="card-summary">${escapeHtml(resource.summary || 'No summary provided yet. Open the record to see its source and notes.')}</p>
    ${tags.length ? `<div class="card-tags">${tags.map(tag => `<span class="card-tag">${escapeHtml(tag)}</span>`).join('')}</div>` : '<div class="card-tags"></div>'}
    <div class="card-footer"><span class="card-author">${escapeHtml(resource.author || 'Author not specified')}${resource.year ? ` · ${escapeHtml(resource.year)}` : ''}</span><button class="card-open" data-open-resource="${Number(resource.id)}">View resource ↗</button></div>
  </article>`;
}

function openResourceModal() {
  $('#resource-form-error').classList.add('hidden');
  $('#resource-modal-backdrop').classList.remove('hidden');
  document.body.style.overflow = 'hidden';
  window.setTimeout(() => $('#resource-title').focus(), 60);
}
function closeModal(backdropId) {
  $(`#${backdropId}`).classList.add('hidden');
  if ($$('.modal-backdrop:not(.hidden)').length === 0) document.body.style.overflow = '';
}

async function openResource(id) {
  try {
    const resource = await requestJson(`/api/resources/${Number(id)}`);
    const title = escapeHtml(resource.title || 'Resource details');
    $('#detail-title').textContent = resource.title || 'Resource details';
    const tags = String(resource.tags || '').split(',').map(tag => tag.trim()).filter(Boolean);
    const hasLink = /^https?:\/\//i.test(resource.url || '');
    const hasFile = Boolean(resource.has_file);
    $('#detail-content').innerHTML = `
      <div class="detail-meta"><span class="detail-pill">${escapeHtml(resource.type)}</span><span class="detail-pill">${escapeHtml(resource.category)}</span><span class="detail-pill">${escapeHtml(resource.region)}</span>${resource.year ? `<span class="detail-pill">${escapeHtml(resource.year)}</span>` : ''}</div>
      <p class="detail-description">${escapeHtml(resource.summary || 'No description provided.')}</p>
      <div class="detail-block"><h4>Author / organisation</h4><div class="detail-notes">${escapeHtml(resource.author || 'Not specified')}</div></div>
      <div class="detail-block"><h4>Research notes / abstract</h4><div class="detail-notes">${escapeHtml(resource.content || 'No notes have been added to this record yet.')}</div></div>
      ${tags.length ? `<div class="detail-block"><h4>Search tags</h4><div class="card-tags">${tags.map(tag => `<span class="card-tag">${escapeHtml(tag)}</span>`).join('')}</div></div>` : ''}
      ${hasLink ? `<div class="detail-block"><h4>Original source</h4><a class="detail-source" href="${escapeHtml(resource.url)}" target="_blank" rel="noreferrer">${escapeHtml(resource.url)}</a></div>` : ''}
      <div class="detail-actions">${hasLink || hasFile ? `<a class="primary-button" href="/api/resources/${Number(id)}/download" target="_blank" rel="noreferrer">${hasFile ? 'Download attached file' : 'Open original source'} <span>↗</span></a>` : ''}<button class="outline-button" data-copy-resource="${Number(id)}">Copy citation details</button></div>`;
    $('#detail-modal-backdrop').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    loadDashboard();
  } catch (error) {
    toast(error.message, 'error', 'Could not open resource');
  }
}

function closeDetail() { closeModal('detail-modal-backdrop'); }

async function handleResourceSubmit(event) {
  event.preventDefault();
  const form = $('#resource-form');
  const button = $('#save-resource');
  const errorBox = $('#resource-form-error');
  errorBox.classList.add('hidden');
  button.disabled = true;
  button.innerHTML = 'Saving…';
  try {
    const data = await requestJson('/api/resources', { method: 'POST', body: new FormData(form) });
    form.reset();
    closeModal('resource-modal-backdrop');
    toast(`“${data.title}” was added to the library.`, 'success', 'Resource saved');
    await loadDashboard();
    if (state.currentPage === 'library') await loadLibrary();
  } catch (error) {
    errorBox.textContent = error.message;
    errorBox.classList.remove('hidden');
  } finally {
    button.disabled = false;
    button.innerHTML = 'Save to library <span>↗</span>';
  }
}

function appendChatEntry(kind, title, content, sources = []) {
  const container = $('#chat-messages');
  const empty = $('.chat-empty', container);
  if (empty) empty.remove();
  const entry = document.createElement('div');
  entry.className = `chat-entry ${kind}`;
  let html = `<div class="chat-entry-label">${escapeHtml(title)}</div><p>${formatSimpleMarkdown(content)}</p>`;
  if (sources.length) {
    html += `<div class="chat-sources">${sources.map(source => {
      const safeUrl = /^https?:\/\//i.test(source.url || '') ? source.url : '';
      return safeUrl ? `<a href="${escapeHtml(safeUrl)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)} ↗</a>` : `<span class="card-tag">${escapeHtml(source.title)}</span>`;
    }).join('')}</div>`;
  }
  entry.innerHTML = html;
  container.appendChild(entry);
  container.scrollTop = container.scrollHeight;
  return entry;
}

async function submitQuestion(question) {
  const clean = String(question || '').trim();
  if (!clean) return;
  state.lastQuestion = clean;
  appendChatEntry('user', 'YOUR QUESTION', clean);
  const placeholder = appendChatEntry('assistant', 'POLAR ASSISTANT', 'Searching the repository for relevant records…');
  const button = $('#ask-submit');
  button.disabled = true;
  button.innerHTML = 'Searching…';
  try {
    const data = await requestJson('/api/ask', {
      method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ question: clean })
    });
    placeholder.querySelector('p').innerHTML = formatSimpleMarkdown(data.answer || 'No answer returned.');
    placeholder.querySelector('.chat-entry-label').textContent = data.mode === 'ai' ? 'POLAR AI · GROUNDED RESPONSE' : 'POLAR ASSISTANT · LOCAL SEARCH';
    const sourceContainer = document.createElement('div');
    sourceContainer.className = 'chat-sources';
    (data.sources || []).forEach(source => {
      const a = document.createElement(source.url ? 'a' : 'span');
      a.textContent = `${source.title}${source.url ? ' ↗' : ''}`;
      if (source.url && /^https?:\/\//i.test(source.url)) { a.href = source.url; a.target = '_blank'; a.rel = 'noreferrer'; }
      else a.className = 'card-tag';
      sourceContainer.appendChild(a);
    });
    if ((data.sources || []).length) placeholder.appendChild(sourceContainer);
    $('#assistant-mode-label').textContent = data.mode === 'ai' ? 'AI-assisted · sources included' : 'Local retrieval mode';
  } catch (error) {
    placeholder.querySelector('p').textContent = `I could not reach the local API: ${error.message}. Make sure the Flask server is running.`;
    placeholder.classList.add('error');
  } finally {
    button.disabled = false;
    button.innerHTML = 'Ask question <span>↗</span>';
    $('#chat-messages').scrollTop = $('#chat-messages').scrollHeight;
  }
}

async function handleStudioSubmit(event) {
  event.preventDefault();
  const topic = $('#studio-topic').value.trim();
  const format = $('input[name="studio-format"]:checked')?.value || 'social';
  const audience = $('#studio-audience').value;
  if (!topic) return;
  const button = $('#studio-submit');
  button.disabled = true;
  button.innerHTML = 'Creating draft…';
  $('#studio-output-title').textContent = 'Creating your draft';
  $('#studio-output').innerHTML = '<div class="output-placeholder"><div class="placeholder-art"><span>✦</span><i></i><b></b></div><h4>Finding the right words…</h4><p>Building a first draft from your topic and the available source records.</p></div>';
  const payload = { topic, format, audience };
  state.lastStudioPayload = payload;
  try {
    const data = await requestJson('/api/generate', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) });
    state.lastDraft = data.content || '';
    $('#studio-output-title').textContent = ({ social: 'Social media draft', classroom: 'Classroom explainer', brief: 'Research brief', newsletter: 'Newsletter draft' })[format] || 'Outreach draft';
    $('#studio-output').innerHTML = `<div class="generated-copy">${formatSimpleMarkdown(state.lastDraft)}</div>${data.sources?.length ? `<div class="chat-sources">${data.sources.map(source => /^https?:\/\//i.test(source.url || '') ? `<a href="${escapeHtml(source.url)}" target="_blank" rel="noreferrer">${escapeHtml(source.title)} ↗</a>` : '').join('')}</div>` : ''}`;
    $('#studio-output-meta').textContent = data.mode === 'ai' ? 'AI-assisted draft · review before use' : 'Starter template · review before use';
    $('#copy-draft').disabled = false;
    $('#regenerate-draft').disabled = false;
    toast('Your draft is ready for review.', 'success', 'Draft created');
  } catch (error) {
    $('#studio-output-title').textContent = 'Could not create draft';
    $('#studio-output').innerHTML = `<p class="detail-description">${escapeHtml(error.message)}</p>`;
  } finally {
    button.disabled = false;
    button.innerHTML = 'Generate draft <span>↗</span>';
  }
}

async function copyText(text) {
  try {
    await navigator.clipboard.writeText(text);
    toast('Copied to clipboard.', 'success', 'Copied');
  } catch (_) {
    const textarea = document.createElement('textarea');
    textarea.value = text;
    textarea.style.position = 'fixed'; textarea.style.opacity = '0';
    document.body.appendChild(textarea); textarea.select();
    const ok = document.execCommand('copy'); textarea.remove();
    toast(ok ? 'Copied to clipboard.' : 'Clipboard access was blocked by the browser.', ok ? 'success' : 'error', ok ? 'Copied' : 'Could not copy');
  }
}

async function setCategoryFilter(category) {
  switchPage('library');
  await loadLibrary();
  const options = Array.from($('#filter-category').options).map(option => option.value);
  if (options.includes(category)) {
    $('#filter-category').value = category;
    await loadLibrary();
  }
}

// Navigation and globally delegated actions.
document.addEventListener('click', event => {
  const pageTarget = event.target.closest('[data-page]');
  if (pageTarget) { switchPage(pageTarget.dataset.page); return; }
  const categoryTarget = event.target.closest('[data-category]');
  if (categoryTarget) { setCategoryFilter(categoryTarget.dataset.category); return; }
  const openTarget = event.target.closest('[data-open-resource]');
  if (openTarget) { openResource(openTarget.dataset.openResource); return; }
  const copyResourceTarget = event.target.closest('[data-copy-resource]');
  if (copyResourceTarget) {
    const id = Number(copyResourceTarget.dataset.copyResource);
    requestJson(`/api/resources/${id}`).then(resource => copyText(`${resource.title}\n${resource.author || 'Author not specified'} (${resource.year || 'n.d.'}). ${resource.url || ''}\nAccessed via Polar Atlas.`)).catch(error => toast(error.message, 'error'));
    return;
  }
});

$('#top-add-resource').addEventListener('click', openResourceModal);
$('#library-add-resource').addEventListener('click', openResourceModal);
$$('.close-modal').forEach(button => button.addEventListener('click', () => closeModal('resource-modal-backdrop')));
$$('.close-detail').forEach(button => button.addEventListener('click', closeDetail));
$('#resource-modal-backdrop').addEventListener('click', event => { if (event.target === event.currentTarget) closeModal('resource-modal-backdrop'); });
$('#detail-modal-backdrop').addEventListener('click', event => { if (event.target === event.currentTarget) closeDetail(); });
$('#resource-form').addEventListener('submit', handleResourceSubmit);
$('#filter-category').addEventListener('change', loadLibrary);
$('#filter-region').addEventListener('change', loadLibrary);
$('#filter-type').addEventListener('change', loadLibrary);
$('#library-search').addEventListener('input', debounce(loadLibrary, 220));
$('#clear-filters').addEventListener('click', () => {
  $('#library-search').value = ''; $('#filter-category').value = ''; $('#filter-region').value = ''; $('#filter-type').value = ''; loadLibrary();
});
$('#global-search').addEventListener('keydown', event => {
  if (event.key === 'Enter') {
    event.preventDefault();
    $('#library-search').value = $('#global-search').value.trim();
    $('#filter-category').value = ''; $('#filter-region').value = ''; $('#filter-type').value = '';
    switchPage('library');
    loadLibrary();
  }
});
$('#mobile-menu').addEventListener('click', () => $('#sidebar').classList.toggle('open'));
$('#help-button').addEventListener('click', () => { $('#about-modal-backdrop').classList.remove('hidden'); document.body.style.overflow = 'hidden'; });
$$('.close-about').forEach(button => button.addEventListener('click', () => closeModal('about-modal-backdrop')));
$('#about-modal-backdrop').addEventListener('click', event => { if (event.target === event.currentTarget) closeModal('about-modal-backdrop'); });

document.addEventListener('keydown', event => {
  if (event.key === 'Escape') {
    closeModal('resource-modal-backdrop'); closeModal('detail-modal-backdrop'); closeModal('about-modal-backdrop');
    $('#sidebar').classList.remove('open');
  }
});

$('#ask-form').addEventListener('submit', event => {
  event.preventDefault();
  const input = $('#ask-question');
  const value = input.value.trim();
  if (!value) return;
  input.value = '';
  submitQuestion(value);
});
$$('.prompt-chip').forEach(button => button.addEventListener('click', () => {
  $('#ask-question').value = button.dataset.question;
  $('#ask-question').focus();
  $('#ask-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
}));

$$('input[name="studio-format"]').forEach(input => input.addEventListener('change', () => {
  $$('.format-option').forEach(option => option.classList.toggle('selected', $('input', option).checked));
}));
$('#studio-form').addEventListener('submit', handleStudioSubmit);
$('#copy-draft').addEventListener('click', () => { if (state.lastDraft) copyText(state.lastDraft); });
$('#regenerate-draft').addEventListener('click', () => {
  if (!state.lastStudioPayload) return;
  $('#studio-topic').value = state.lastStudioPayload.topic;
  $('#studio-audience').value = state.lastStudioPayload.audience;
  const radio = $(`input[name="studio-format"][value="${state.lastStudioPayload.format}"]`);
  if (radio) { radio.checked = true; $$('.format-option').forEach(option => option.classList.toggle('selected', $('input', option).checked)); }
  $('#studio-form').dispatchEvent(new Event('submit', { bubbles: true, cancelable: true }));
});

function debounce(fn, delay) {
  let timer;
  return (...args) => { clearTimeout(timer); timer = setTimeout(() => fn(...args), delay); };
}

// Initialise metrics and collection counts at page load.
loadDashboard();
loadLibrary();
