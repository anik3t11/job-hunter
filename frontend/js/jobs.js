/* ── Load & render jobs ── */
async function loadJobs(page = State.page) {
  State.page = page;
  const f = State.filters;
  const params = new URLSearchParams({ page, per_page: State.perPage, sort: f.sort });
  if (f.status && f.status !== 'all') params.set('status', f.status);
  if (f.source && f.source !== 'all') params.set('source', f.source);
  if (f.minScore === '70') params.set('min_score', 70);
  else if (f.minScore === '40') params.set('min_score', 40);

  try {
    const data = await api('GET', `/api/jobs?${params}`);
    let jobs = data.jobs;
    if (f.minScore === '40') jobs = jobs.filter(j => j.match_score >= 40 && j.match_score < 70);
    if (f.minScore === '0')  jobs = jobs.filter(j => j.match_score < 40);

    State.jobs = jobs;
    State.total = data.total;
    renderJobs(jobs);
    renderPagination(data.total, page, State.perPage);
    refreshStats();
  } catch (err) {
    showToast(`Failed to load jobs: ${err.message}`, 'error');
  }
}

function renderJobs(jobs) {
  const grid = document.getElementById('jobs-grid');
  if (!jobs.length) {
    grid.innerHTML = `<div class="empty-state" id="empty-state">
      <div class="empty-icon">📋</div>
      <p>No jobs found. Try adjusting your filters or run a new search.</p>
    </div>`;
    return;
  }
  grid.innerHTML = jobs.map(jobCard).join('');

  grid.querySelectorAll('.view-btn').forEach(b =>
    b.addEventListener('click', () => openJobDetail(+b.dataset.id)));
  grid.querySelectorAll('.apply-btn').forEach(b =>
    b.addEventListener('click', () => {
      window.open(b.dataset.url, '_blank');
      if (b.dataset.status === 'new') updateJobStatus(+b.dataset.id, 'applied');
    }));
  grid.querySelectorAll('.email-btn').forEach(b =>
    b.addEventListener('click', () => openEmailModal(+b.dataset.id, 'cold')));
  grid.querySelectorAll('.status-select').forEach(sel =>
    sel.addEventListener('change', async () => {
      await updateJobStatus(+sel.dataset.id, sel.value);
      sel.className = `status-select status-${sel.value}`;
    }));
}

function jobCard(job) {
  const salary  = formatSalary(job.salary_min, job.salary_max, job.salary_raw);
  const gap     = job.skills_gap ? job.skills_gap.split(',').map(s => s.trim()).filter(Boolean) : [];
  const stretch = job.skills_stretch ? job.skills_stretch.split(',').map(s => s.trim()).filter(Boolean) : [];
  const gapHtml = gap.length
    ? `<div class="skills-gap-row">
        <span class="skills-gap-label">Gap:</span>
        ${gap.slice(0,5).map(s => `<span class="gap-chip">${escHtml(s)}</span>`).join('')}
       </div>`
    : '';
  const stretchHtml = stretch.length
    ? `<div class="skills-gap-row">
        <span class="skills-gap-label stretch-label">Transferable:</span>
        ${stretch.slice(0,4).map(s => `<span class="stretch-chip">${escHtml(s)}</span>`).join('')}
       </div>`
    : '';
  const hotBadge     = job.is_hot    ? `<span class="hot-badge">🔥 HOT</span>` : '';
  const stretchBadge = job.is_stretch ? `<span class="stretch-badge">STRETCH</span>` : '';
  const variantBadge = job.role_variant
    ? `<span class="variant-badge" title="Found via role variant">via: ${escHtml(job.role_variant)}</span>` : '';
  const emailBtn = job.recruiter_email
    ? `<button class="btn btn-sm btn-secondary email-btn" data-id="${job.id}">✉ Email</button>` : '';

  return `
    <div class="job-card status-${job.status}" data-id="${job.id}">
      <div class="card-badges">${hotBadge}${stretchBadge}${variantBadge}</div>
      <div class="card-header">
        <div class="card-source-row">
          ${sourceBadge(job.source)}
          ${scorePill(job.match_score)}
        </div>
        <select class="status-select status-${job.status}" data-id="${job.id}">
          <option value="new"       ${job.status==='new'?'selected':''}>New</option>
          <option value="reviewed"  ${job.status==='reviewed'?'selected':''}>Reviewed</option>
          <option value="applied"   ${job.status==='applied'?'selected':''}>Applied</option>
          <option value="interview" ${job.status==='interview'?'selected':''}>Interview</option>
        </select>
      </div>
      <div>
        <div class="job-title">${escHtml(job.title)}</div>
        <div class="job-company">${escHtml(job.company)}</div>
      </div>
      <div class="job-meta">
        ${chip('📍', job.location)}
        ${chip('💰', salary)}
        ${chip('🧑‍💼', job.experience_required)}
      </div>
      ${job.description_snippet
        ? `<div class="job-snippet">${escHtml(job.description_snippet)}…</div>` : ''}
      ${gapHtml}
      ${stretchHtml}
      <div class="card-footer">
        <div class="card-actions">
          <button class="btn btn-sm btn-ghost view-btn" data-id="${job.id}">Details</button>
          <button class="btn btn-sm btn-primary apply-btn"
            data-id="${job.id}" data-url="${escAttr(job.job_url)}" data-status="${job.status}">
            Apply ↗
          </button>
          ${emailBtn}
        </div>
      </div>
    </div>`;
}

async function openJobDetail(jobId) {
  try {
    const job = await api('GET', `/api/jobs/${jobId}`);
    const salary = formatSalary(job.salary_min, job.salary_max, job.salary_raw);
    const bd = typeof job.match_breakdown === 'object' ? job.match_breakdown : {};
    const gap = job.skills_gap ? job.skills_gap.split(',').map(s=>s.trim()).filter(Boolean) : [];

    const bkHtml = Object.entries(bd).map(([k,v]) =>
      `<span class="breakdown-item">${k}: ${v}</span>`).join('');

    const gapSection = gap.length
      ? `<div><h4>Skills Gap (add these to your resume)</h4>
         <div class="job-meta">${gap.map(s=>`<span class="gap-chip">${escHtml(s)}</span>`).join('')}</div></div>`
      : '';

    const emailBtn = job.recruiter_email
      ? `<button class="btn btn-secondary" onclick="closeModal();openEmailModal(${job.id},'cold')">✉ Cold Email</button>` : '';

    openModal(`
      <div style="display:flex;align-items:flex-start;justify-content:space-between;gap:.5rem;margin-bottom:.75rem">
        <div style="flex:1">
          <div class="detail-company">${escHtml(job.company)} · ${sourceBadge(job.source)}</div>
          <div class="detail-title">${escHtml(job.title)}</div>
        </div>
        ${scorePill(job.match_score)}
      </div>
      <div class="detail-meta">
        ${chip('📍', job.location)}
        ${chip('💰', salary)}
        ${chip('🧑‍💼', job.experience_required)}
        ${chip('🗓', job.scraped_at ? new Date(job.scraped_at).toLocaleDateString() : '')}
      </div>
      ${bkHtml ? `<div class="score-breakdown">${bkHtml}</div>` : ''}
      ${job.recruiter_email ? `<div style="margin:.5rem 0;font-size:.85rem">📧 <a href="mailto:${escAttr(job.recruiter_email)}">${escHtml(job.recruiter_email)}</a></div>` : ''}
      ${job.skills_required ? `<div><h4 class="detail-body" style="font-size:.82rem;font-weight:700;color:var(--slate);margin:.75rem 0 .3rem">Skills</h4><p style="font-size:.82rem;color:var(--muted)">${escHtml(job.skills_required)}</p></div>` : ''}
      ${gapSection}
      <div class="detail-body">
        <h4>Description</h4>
        <div class="detail-description">${escHtml(job.description || 'No description available.')}</div>
      </div>
      <div class="detail-actions">
        <a href="${escAttr(job.job_url)}" target="_blank" class="btn btn-primary">Apply ↗</a>
        ${emailBtn}
        <select class="status-select status-${job.status}"
          onchange="updateJobStatus(${job.id},this.value);this.className='status-select status-'+this.value">
          <option value="new"       ${job.status==='new'?'selected':''}>New</option>
          <option value="reviewed"  ${job.status==='reviewed'?'selected':''}>Reviewed</option>
          <option value="applied"   ${job.status==='applied'?'selected':''}>Applied</option>
          <option value="interview" ${job.status==='interview'?'selected':''}>Interview</option>
        </select>
      </div>
    `);
  } catch (err) {
    showToast(`Could not load job: ${err.message}`, 'error');
  }
}

async function updateJobStatus(jobId, status) {
  try {
    await api('PATCH', `/api/jobs/${jobId}`, { status });
    const card = document.querySelector(`.job-card[data-id="${jobId}"]`);
    if (card) card.className = `job-card status-${status}`;
    refreshStats();
  } catch (err) {
    showToast(`Update failed: ${err.message}`, 'error');
  }
}

/* ── Pagination ── */
function renderPagination(total, cur, perPage) {
  const pages = Math.ceil(total / perPage);
  const el = document.getElementById('pagination');
  if (pages <= 1) { el.innerHTML = ''; return; }
  let html = `<button class="page-btn" ${cur===1?'disabled':''} onclick="loadJobs(${cur-1})">‹</button>`;
  for (let i = 1; i <= pages; i++) {
    if (i===1||i===pages||Math.abs(i-cur)<=1)
      html += `<button class="page-btn ${i===cur?'active':''}" onclick="loadJobs(${i})">${i}</button>`;
    else if (Math.abs(i-cur)===2)
      html += `<span class="page-btn" style="cursor:default">…</span>`;
  }
  html += `<button class="page-btn" ${cur===pages?'disabled':''} onclick="loadJobs(${cur+1})">›</button>`;
  el.innerHTML = html;
}

/* ── Search form ── */
document.addEventListener('DOMContentLoaded', () => {
  const form = document.getElementById('search-form');
  const statusEl = document.getElementById('search-status');

  form.addEventListener('submit', async e => {
    e.preventDefault();
    const role    = document.getElementById('s-role').value.trim();
    const country = document.getElementById('s-country').value;
    const salary  = parseInt(document.getElementById('s-salary').value) || 0;
    const exp     = parseFloat(document.getElementById('s-exp').value) || 0;
    const locs    = locationTags.getValues();
    const sources = [...document.querySelectorAll('input[name=source]:checked')].map(c => c.value);

    if (!sources.length) { showToast('Select at least one source.', 'error'); return; }
    if (!locs.length) { showToast('Add at least one location.', 'error'); return; }

    const btn = document.getElementById('search-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Searching…`;
    statusEl.className = 'search-status info';
    statusEl.textContent = `Searching ${sources.join(', ')} in ${locs.join(', ')}… (30–90 seconds)`;
    statusEl.classList.remove('hidden');

    try {
      const result = await api('POST', '/api/search', {
        role, locations: locs, country,
        salary_target: salary,
        experience_years: exp,
        sources,
      });

      let msg = `Found ${result.jobs_found} jobs — ${result.jobs_new} new, ${result.jobs_duplicate} duplicates.`;
      if (result.errors?.length) {
        msg += ' ⚠ ' + result.errors.map(e => `${e.source}: ${e.message}`).join('; ');
        statusEl.className = 'search-status warning';
      } else {
        statusEl.className = 'search-status success';
      }
      statusEl.textContent = msg;

      // Show which role variants were searched
      const varInfo = document.getElementById('variants-info');
      if (result.role_variants_searched?.length > 1) {
        varInfo.textContent = `Also searched: ${result.role_variants_searched.slice(1).join(', ')}`;
        varInfo.classList.remove('hidden');
      } else {
        varInfo.classList.add('hidden');
      }

      loadJobs(1);
    } catch (err) {
      statusEl.className = 'search-status error';
      statusEl.textContent = `Search failed: ${err.message}`;
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span class="btn-icon">🔍</span> Search Jobs`;
    }
  });

  document.getElementById('clear-btn').addEventListener('click', async () => {
    if (!confirm('Delete all saved jobs? Cannot be undone.')) return;
    try {
      await api('DELETE', '/api/jobs/clear/all');
      showToast('All jobs cleared.', 'info');
      loadJobs(1);
    } catch (err) { showToast(err.message, 'error'); }
  });

  // Filter tabs
  ['status-tabs','source-tabs'].forEach(id => {
    document.getElementById(id).addEventListener('click', e => {
      if (!e.target.classList.contains('tab')) return;
      e.target.closest('.filter-tabs').querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
      e.target.classList.add('active');
      State.filters[id === 'status-tabs' ? 'status' : 'source'] = e.target.dataset.value;
      loadJobs(1);
    });
  });

  document.getElementById('score-tabs').addEventListener('click', e => {
    if (!e.target.classList.contains('tab')) return;
    e.target.closest('.filter-tabs').querySelectorAll('.tab').forEach(t => t.classList.remove('active'));
    e.target.classList.add('active');
    State.filters.minScore = e.target.dataset.value || null;
    loadJobs(1);
  });

  document.getElementById('sort-select').addEventListener('change', e => {
    State.filters.sort = e.target.value;
    loadJobs(1);
  });
});
