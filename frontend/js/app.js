/* ── Global state ── */
const State = {
  currentPage: 'jobs',
  jobs: [],
  total: 0,
  page: 1,
  perPage: 20,
  filters: { status: 'all', source: 'all', minScore: null, sort: 'score' },
};

/* ── API client ── */
async function api(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-cache' },
  };
  if (body) opts.body = JSON.stringify(body);
  const resp = await fetch(path, opts);
  if (!resp.ok) {
    const err = await resp.json().catch(() => ({ detail: resp.statusText }));
    throw new Error(err.detail || 'Request failed');
  }
  return resp.json();
}

/* ── Toast ── */
let _toastTimer;
function showToast(msg, type = 'info') {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.className = `toast ${type}`;
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => el.classList.add('hidden'), 3800);
}

/* ── Router ── */
function navigate(page) {
  document.querySelectorAll('.page').forEach(p => p.classList.add('hidden'));
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  const target = document.getElementById(`page-${page}`);
  if (target) target.classList.remove('hidden');
  const link = document.querySelector(`.nav-link[data-page="${page}"]`);
  if (link) link.classList.add('active');
  State.currentPage = page;
  if (page === 'tracker')  renderTracker();
  if (page === 'followup') renderFollowups();
  if (page === 'outreach') loadSocialPosts(1);
  if (page === 'settings') loadSettings();
  if (page === 'jobs')     loadJobs();
}

/* ── Navbar stats ── */
async function refreshStats() {
  try {
    const s = await api('GET', '/api/jobs/stats');
    const el = document.getElementById('navbar-stats');
    el.innerHTML = `
      <span class="stat-pill">📋 ${s.total_jobs || 0} jobs</span>
      <span class="stat-pill">✅ ${s.by_status?.applied || 0} applied</span>
      <span class="stat-pill">🎤 ${s.by_status?.interview || 0} interviews</span>
    `;
    // Follow-up badge
    const due = s.followup_due || 0;
    const badge = document.getElementById('followup-badge');
    badge.textContent = due;
    badge.classList.toggle('hidden', due === 0);
  } catch (_) {}
}

/* ── Helpers ── */
function scorePill(score) {
  const cls = score >= 70 ? 'high' : score >= 40 ? 'medium' : 'low';
  return `<span class="score-pill ${cls}">${score}</span>`;
}
function sourceBadge(source) {
  const labels = { linkedin:'LinkedIn', naukri:'Naukri', indeed:'Indeed', foundit:'Foundit', wellfound:'Wellfound' };
  return `<span class="source-badge ${source}">${labels[source] || source}</span>`;
}
function chip(icon, text) {
  return text ? `<span class="meta-chip">${icon} ${escHtml(text)}</span>` : '';
}
function formatSalary(min, max, raw) {
  if (raw && raw.trim()) return raw;
  if (!min && !max) return '';
  const fmt = n => n >= 100000 ? `₹${(n/100000).toFixed(1)}L` : `₹${n.toLocaleString()}`;
  if (min && max) return `${fmt(min)} – ${fmt(max)}`;
  if (min) return `${fmt(min)}+`;
  if (max) return `up to ${fmt(max)}`;
  return '';
}
function escHtml(s) {
  if (!s) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function escAttr(s) { return String(s||'').replace(/"/g,'&quot;'); }

/* ── Init ── */
document.addEventListener('DOMContentLoaded', () => {
  // Tag input + sources
  locationTags = new TagInput('location-tag-wrapper','location-input','city-suggestions','s-country');
  renderSourceCheckboxes('IN');

  // Hash router
  const handleHash = () => {
    const page = location.hash.replace('#','') || 'jobs';
    navigate(['jobs','outreach','tracker','followup','settings'].includes(page) ? page : 'jobs');
  };
  window.addEventListener('hashchange', handleHash);
  handleHash();

  // Nav links
  document.querySelectorAll('.nav-link').forEach(l => {
    l.addEventListener('click', e => { e.preventDefault(); location.hash = l.dataset.page; });
  });

  // Modal close
  document.getElementById('modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeModal();
  });
  document.getElementById('email-modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeEmailModal();
  });
  document.getElementById('modal-close-btn').addEventListener('click', closeModal);
  document.getElementById('email-modal-close').addEventListener('click', closeEmailModal);
  document.getElementById('email-cancel-btn').addEventListener('click', closeEmailModal);
  document.addEventListener('keydown', e => {
    if (e.key === 'Escape') { closeModal(); closeEmailModal(); }
  });

  refreshStats();
  setInterval(refreshStats, 30000);
});

/* ── Modal helpers ── */
function openModal(html) {
  document.getElementById('modal-content').innerHTML = html;
  document.getElementById('modal-overlay').classList.remove('hidden');
}
function closeModal() { document.getElementById('modal-overlay').classList.add('hidden'); }
function closeEmailModal() { document.getElementById('email-modal-overlay').classList.add('hidden'); }
