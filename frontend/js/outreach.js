/* ── Outreach / Social Hiring Posts ── */

const OutreachState = {
  filters: { source: 'all', status: 'all', country: 'all' },
  page: 1,
  perPage: 20,
};

const PLATFORM_LABELS = {
  linkedin_post: { icon: '💼', label: 'LinkedIn' },
  reddit:        { icon: '🤖', label: 'Reddit' },
  twitter:       { icon: '🐦', label: 'Twitter' },
};

function platformBadge(source) {
  const p = PLATFORM_LABELS[source] || { icon: '🌐', label: source };
  return `<span class="source-badge source-${source}">${p.icon} ${p.label}</span>`;
}

async function loadSocialPosts(page = OutreachState.page) {
  OutreachState.page = page;
  const f = OutreachState.filters;
  const params = new URLSearchParams({ page, per_page: OutreachState.perPage });
  if (f.source !== 'all') params.set('source', f.source);
  if (f.status !== 'all') params.set('status', f.status);
  if (f.country !== 'all') params.set('country', f.country);

  try {
    const data = await api('GET', `/api/social/posts?${params}`);
    renderSocialPosts(data.posts);
    renderSocialPagination(data.total, page, OutreachState.perPage);

    const badge = document.getElementById('outreach-badge');
    if (data.total > 0) {
      badge.textContent = data.total;
      badge.classList.remove('hidden');
    } else {
      badge.classList.add('hidden');
    }
  } catch (err) {
    showToast(`Failed to load posts: ${err.message}`, 'error');
  }
}

function renderSocialPosts(posts) {
  const grid = document.getElementById('social-grid');
  if (!posts.length) {
    grid.innerHTML = `<div class="empty-state" id="social-empty">
      <div class="empty-icon">📡</div>
      <p>No posts yet. Search above to find recruiters actively hiring.</p>
    </div>`;
    return;
  }
  grid.innerHTML = posts.map(socialCard).join('');

  grid.querySelectorAll('.outreach-email-btn').forEach(btn =>
    btn.addEventListener('click', () => openOutreachEmail(+btn.dataset.id)));
  grid.querySelectorAll('.outreach-dismiss-btn').forEach(btn =>
    btn.addEventListener('click', () => dismissPost(+btn.dataset.id)));
  grid.querySelectorAll('.outreach-contacted-btn').forEach(btn =>
    btn.addEventListener('click', () => markContacted(+btn.dataset.id)));
}

function legitimacyBar(score) {
  const pct = Math.min(score || 0, 100);
  const color = pct >= 70 ? '#059669' : pct >= 40 ? '#d97706' : '#e11d48';
  const label = pct >= 70 ? 'High' : pct >= 40 ? 'Medium' : 'Low';
  return `
    <div class="legitimacy-row" title="Legitimacy score: ${pct}/100">
      <span class="legitimacy-label">Legitimacy</span>
      <div class="legitimacy-track">
        <div class="legitimacy-fill" style="width:${pct}%;background:${color}"></div>
      </div>
      <span class="legitimacy-val" style="color:${color}">${label} (${pct})</span>
    </div>`;
}

function socialCard(post) {
  const isNew       = post.status === 'new';
  const isDismissed = post.status === 'dismissed';
  const timeAgo     = post.scraped_at ? timeAgoStr(post.scraped_at) : '';

  const emailLine = post.poster_email
    ? `<div class="post-email">📧 <a href="mailto:${escAttr(post.poster_email)}">${escHtml(post.poster_email)}</a></div>`
    : '';

  const profileLink = post.poster_profile_url
    ? `<a href="${escAttr(post.poster_profile_url)}" target="_blank" class="post-profile-link">
        ${escHtml(post.poster_name || 'View Profile')} ↗
       </a>`
    : (post.poster_name ? `<span class="post-profile-link">${escHtml(post.poster_name)}</span>` : '');

  return `
    <div class="social-card ${isDismissed ? 'dismissed' : ''}" data-id="${post.id}">
      <div class="card-header">
        <div class="card-source-row">
          ${platformBadge(post.source)}
          ${post.role_mentioned ? `<span class="role-chip">${escHtml(post.role_mentioned)}</span>` : ''}
        </div>
        <span class="post-time">${timeAgo}</span>
      </div>
      <div class="post-poster-row">
        ${profileLink}
        ${post.company ? `<span class="post-company">@ ${escHtml(post.company)}</span>` : ''}
      </div>
      <div class="post-text">${escHtml((post.post_text || '').slice(0, 300))}${post.post_text?.length > 300 ? '…' : ''}</div>
      ${emailLine}
      ${legitimacyBar(post.legitimacy_score)}
      <div class="card-footer">
        <div class="card-actions">
          <a href="${escAttr(post.post_url)}" target="_blank" class="btn btn-sm btn-ghost">View Post ↗</a>
          ${post.poster_email
            ? `<button class="btn btn-sm btn-primary outreach-email-btn" data-id="${post.id}">✉ Email</button>`
            : `<button class="btn btn-sm btn-secondary outreach-email-btn" data-id="${post.id}">✉ Compose</button>`}
          ${isNew
            ? `<button class="btn btn-sm btn-ghost outreach-contacted-btn" data-id="${post.id}">✓ Mark Contacted</button>` : ''}
          ${!isDismissed
            ? `<button class="btn btn-sm btn-ghost outreach-dismiss-btn" data-id="${post.id}" title="Dismiss">✕</button>` : ''}
        </div>
      </div>
    </div>`;
}

async function openOutreachEmail(postId) {
  try {
    const data = await api('POST', `/api/social/posts/${postId}/email`);
    openEmailModal(null, 'outreach', {
      to: data.to,
      subject: data.subject,
      body: data.body,
      post: data.post,
    });
  } catch (err) {
    showToast(`Could not build template: ${err.message}`, 'error');
  }
}

async function dismissPost(postId) {
  try {
    await api('PATCH', `/api/social/posts/${postId}`, { status: 'dismissed' });
    const card = document.querySelector(`.social-card[data-id="${postId}"]`);
    if (card) card.classList.add('dismissed');
    showToast('Post dismissed.', 'info');
  } catch (err) {
    showToast(err.message, 'error');
  }
}

async function markContacted(postId) {
  try {
    await api('PATCH', `/api/social/posts/${postId}`, { status: 'contacted' });
    showToast('Marked as contacted.', 'success');
    loadSocialPosts();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

function renderSocialPagination(total, cur, perPage) {
  const pages = Math.ceil(total / perPage);
  const el = document.getElementById('social-pagination');
  if (pages <= 1) { el.innerHTML = ''; return; }
  let html = `<button class="page-btn" ${cur===1?'disabled':''} onclick="loadSocialPosts(${cur-1})">‹</button>`;
  for (let i = 1; i <= pages; i++) {
    if (i===1||i===pages||Math.abs(i-cur)<=1)
      html += `<button class="page-btn ${i===cur?'active':''}" onclick="loadSocialPosts(${i})">${i}</button>`;
    else if (Math.abs(i-cur)===2)
      html += `<span class="page-btn" style="cursor:default">…</span>`;
  }
  html += `<button class="page-btn" ${cur===pages?'disabled':''} onclick="loadSocialPosts(${cur+1})">›</button>`;
  el.innerHTML = html;
}

function timeAgoStr(isoStr) {
  try {
    const diff = Date.now() - new Date(isoStr).getTime();
    const mins = Math.floor(diff / 60000);
    if (mins < 60) return `${mins}m ago`;
    const hrs = Math.floor(mins / 60);
    if (hrs < 24) return `${hrs}h ago`;
    return `${Math.floor(hrs / 24)}d ago`;
  } catch { return ''; }
}

document.addEventListener('DOMContentLoaded', () => {
  // Search button
  document.getElementById('social-search-btn').addEventListener('click', async () => {
    const role    = document.getElementById('social-role').value.trim();
    const country = document.getElementById('social-country').value;
    const sources = [...document.querySelectorAll('#page-outreach input[type=checkbox]:checked')].map(c => c.value);

    if (!role) { showToast('Enter a role to search for.', 'error'); return; }

    const btn = document.getElementById('social-search-btn');
    const statusEl = document.getElementById('social-status');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Searching…`;
    statusEl.className = 'search-status info';
    statusEl.textContent = 'Scanning LinkedIn posts, Reddit, and Twitter… (15–30 seconds)';
    statusEl.classList.remove('hidden');

    try {
      const result = await api('POST', '/api/social/search', { role, country, sources });
      statusEl.className = 'search-status success';
      statusEl.textContent = `Found ${result.found} posts — ${result.inserted} new.`;
      loadSocialPosts(1);
    } catch (err) {
      statusEl.className = 'search-status error';
      statusEl.textContent = `Search failed: ${err.message}`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span class="btn-icon">📡</span> Find Posts`;
    }
  });

  // Platform filter tabs
  document.getElementById('social-source-tabs').addEventListener('click', e => {
    if (!e.target.classList.contains('tab')) return;
    e.target.closest('.filter-tabs').querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    OutreachState.filters.source = e.target.dataset.value;
    loadSocialPosts(1);
  });

  // Status filter tabs
  document.getElementById('social-status-tabs').addEventListener('click', e => {
    if (!e.target.classList.contains('tab')) return;
    e.target.closest('.filter-tabs').querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    OutreachState.filters.status = e.target.dataset.value;
    loadSocialPosts(1);
  });
});
