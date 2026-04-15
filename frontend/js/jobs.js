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
    grid.innerHTML = `<div class="empty-state">
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
  grid.querySelectorAll('.recruiter-btn').forEach(b =>
    b.addEventListener('click', () => openRecruiterFinder(b.dataset.company)));
  grid.querySelectorAll('.insights-btn').forEach(b =>
    b.addEventListener('click', () => openCompanyInsights(b.dataset.company, b.dataset.role)));
  grid.querySelectorAll('.ai-cover-btn').forEach(b =>
    b.addEventListener('click', () => openAiModal(+b.dataset.id, 'cover')));
  grid.querySelectorAll('.status-select').forEach(sel =>
    sel.addEventListener('change', async () => {
      await updateJobStatus(+sel.dataset.id, sel.value);
      sel.className = `status-select status-${sel.value}`;
    }));
}

function statusOptions(current) {
  const opts = ['new','reviewed','applied','interview','offer','rejected'];
  return opts.map(o =>
    `<option value="${o}" ${current===o?'selected':''}>${o.charAt(0).toUpperCase()+o.slice(1)}</option>`
  ).join('');
}

function jobCard(job) {
  const salary     = formatSalary(job.salary_min, job.salary_max, job.salary_raw);
  const gap        = job.skills_gap ? job.skills_gap.split(',').map(s => s.trim()).filter(Boolean) : [];
  const stretch    = job.skills_stretch ? job.skills_stretch.split(',').map(s => s.trim()).filter(Boolean) : [];
  const gapHtml    = gap.length
    ? `<div class="skills-gap-row"><span class="skills-gap-label">Gap:</span>${gap.slice(0,5).map(s=>`<span class="gap-chip">${escHtml(s)}</span>`).join('')}</div>` : '';
  const stretchHtml = stretch.length
    ? `<div class="skills-gap-row"><span class="skills-gap-label stretch-label">Transferable:</span>${stretch.slice(0,4).map(s=>`<span class="stretch-chip">${escHtml(s)}</span>`).join('')}</div>` : '';

  const hotBadge     = job.is_hot     ? `<span class="hot-badge">🔥 HOT</span>` : '';
  const stretchBadge = job.is_stretch ? `<span class="stretch-badge">STRETCH</span>` : '';
  const variantBadge = job.role_variant
    ? `<span class="variant-badge" title="Found via role variant">via: ${escHtml(job.role_variant)}</span>` : '';

  const emailBtn = job.recruiter_email
    ? `<button class="btn btn-sm btn-secondary email-btn" data-id="${job.id}">✉ Email</button>`
    : `<button class="btn btn-sm btn-ghost recruiter-btn" data-company="${escAttr(job.company)}" title="Find recruiter">Find Recruiter</button>`;

  const insightsBtn = job.company
    ? `<button class="btn btn-sm btn-ghost insights-btn" data-company="${escAttr(job.company)}" data-role="${escAttr(job.title)}" title="Company insights">🏢 Insights</button>` : '';

  return `
    <div class="job-card status-${job.status}" data-id="${job.id}">
      <div class="card-badges">${hotBadge}${stretchBadge}${variantBadge}</div>
      <div class="card-header">
        <div class="card-source-row">
          ${sourceBadge(job.source)}
          ${scorePill(job.match_score)}
        </div>
        <select class="status-select status-${job.status}" data-id="${job.id}">
          ${statusOptions(job.status)}
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
      ${job.description_snippet ? `<div class="job-snippet">${escHtml(job.description_snippet)}…</div>` : ''}
      ${gapHtml}${stretchHtml}
      <div class="card-footer">
        <div class="card-actions">
          <button class="btn btn-sm btn-ghost view-btn" data-id="${job.id}">Details</button>
          <button class="btn btn-sm btn-primary apply-btn"
            data-id="${job.id}" data-url="${escAttr(job.job_url)}" data-status="${job.status}">Apply ↗</button>
          ${emailBtn}
          ${insightsBtn}
          <button class="btn btn-sm btn-ai ai-cover-btn" data-id="${job.id}" title="AI: Generate cover letter">✨ Cover Letter</button>
        </div>
      </div>
    </div>`;
}

async function openJobDetail(jobId) {
  try {
    const job = await api('GET', `/api/jobs/${jobId}`);
    const salary = formatSalary(job.salary_min, job.salary_max, job.salary_raw);
    const bd  = typeof job.match_breakdown === 'object' ? job.match_breakdown : {};
    const gap = job.skills_gap ? job.skills_gap.split(',').map(s=>s.trim()).filter(Boolean) : [];

    const bkHtml  = Object.entries(bd).map(([k,v]) => `<span class="breakdown-item">${k}: ${v}</span>`).join('');
    const gapSection = gap.length
      ? `<div><h4>Skills Gap</h4><div class="job-meta">${gap.map(s=>`<span class="gap-chip">${escHtml(s)}</span>`).join('')}</div></div>` : '';

    const emailBtn = job.recruiter_email
      ? `<button class="btn btn-secondary" onclick="closeModal();openEmailModal(${job.id},'cold')">✉ Cold Email</button>` : '';
    const recruiterBtn = !job.recruiter_email && job.company
      ? `<button class="btn btn-ghost" onclick="closeModal();openRecruiterFinder('${escAttr(job.company)}')">Find Recruiter</button>` : '';
    const insightsBtn = job.company
      ? `<button class="btn btn-ghost" onclick="openCompanyInsights('${escAttr(job.company)}','${escAttr(job.title)}')">🏢 Insights</button>` : '';

    openModal(`
      <div class="detail-header">
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
      ${job.recruiter_email ? `<div class="recruiter-email-row">📧 <a href="mailto:${escAttr(job.recruiter_email)}">${escHtml(job.recruiter_email)}</a></div>` : ''}
      ${job.skills_required ? `<div class="detail-section"><h4>Skills Required</h4><p class="detail-text">${escHtml(job.skills_required)}</p></div>` : ''}
      ${gapSection}
      <div class="detail-body">
        <h4>Description</h4>
        <div class="detail-description">${escHtml(job.description || 'No description available.')}</div>
      </div>
      <div class="detail-actions">
        <a href="${escAttr(job.job_url)}" target="_blank" class="btn btn-primary">Apply ↗</a>
        ${emailBtn}${recruiterBtn}${insightsBtn}
        <button class="btn btn-ai" onclick="openAiModal(${job.id},'cover')">✨ Cover Letter</button>
        <button class="btn btn-ghost" onclick="openAiModal(${job.id},'tailor')">📝 Tailor Resume</button>
        <select class="status-select status-${job.status}"
          onchange="updateJobStatus(${job.id},this.value);this.className='status-select status-'+this.value">
          ${statusOptions(job.status)}
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

/* ── Company Insights ── */
async function openCompanyInsights(company, role) {
  openModal(`<div class="insights-loading"><span class="spinner"></span> Loading company insights for <strong>${escHtml(company)}</strong>…</div>`);
  try {
    const params = new URLSearchParams({ name: company, role: role || '' });
    const d = await api('GET', `/api/company/insights?${params}`);
    const salaryLine = d.avg_salary_min || d.avg_salary_max
      ? `<p>${formatSalary(d.avg_salary_min, d.avg_salary_max, '')} avg for ${escHtml(role||'this role')}</p>` : '<p>Salary data not found.</p>';
    const ratingLine = d.rating ? `<p>⭐ ${d.rating} / 5 — ${d.review_count || 0} reviews</p>` : '';
    const summaryLine = d.review_summary ? `<p class="detail-text">${escHtml(d.review_summary)}</p>` : '';

    openModal(`
      <div class="detail-title" style="margin-bottom:.75rem">🏢 ${escHtml(company)}</div>
      <div class="insights-panel">
        <div class="insights-section">
          <h4>Salary Insights</h4>
          ${salaryLine}
        </div>
        ${ratingLine || summaryLine ? `<div class="insights-section">
          <h4>Company Reviews</h4>
          ${ratingLine}
          ${summaryLine}
        </div>` : ''}
        ${d.error ? `<p class="auth-error" style="display:block">${escHtml(d.error)}</p>` : ''}
      </div>
    `);
  } catch (err) {
    openModal(`<p class="auth-error" style="display:block">Could not load insights: ${escHtml(err.message)}</p>`);
  }
}

/* ── Recruiter Finder ── */
async function openRecruiterFinder(company) {
  openModal(`<div class="insights-loading"><span class="spinner"></span> Searching for recruiters at <strong>${escHtml(company)}</strong>…</div>`);
  try {
    const params = new URLSearchParams({ company });
    const d = await api('GET', `/api/recruiter/find?${params}`);

    const genericHtml = d.generic_emails.map(e =>
      `<span class="gap-chip" style="cursor:pointer" onclick="navigator.clipboard.writeText('${escAttr(e)}');showToast('Copied!','success')">${escHtml(e)}</span>`
    ).join('');

    const candidatesHtml = d.candidates.length
      ? d.candidates.map(c => `
          <div class="recruiter-card">
            <div class="recruiter-name">
              <a href="${escAttr(c.profile_url)}" target="_blank">${escHtml(c.name)} ↗</a>
            </div>
            ${c.snippet ? `<p class="detail-text">${escHtml(c.snippet.slice(0,150))}</p>` : ''}
            ${c.email_guesses.length ? `<div class="recruiter-emails">
              ${c.email_guesses.slice(0,3).map(e =>
                `<span class="gap-chip" style="cursor:pointer" onclick="navigator.clipboard.writeText('${escAttr(e)}');showToast('Copied!','success')">${escHtml(e)}</span>`
              ).join('')}
            </div>` : ''}
          </div>`) .join('')
      : '<p class="detail-text">No LinkedIn profiles found — try generic emails below.</p>';

    openModal(`
      <div class="detail-title" style="margin-bottom:.75rem">Recruiter Contacts — ${escHtml(company)}</div>
      <p class="section-sub">Click any email to copy it to clipboard.</p>
      <h4>LinkedIn Profiles Found</h4>
      <div class="recruiter-list">${candidatesHtml}</div>
      <h4 style="margin-top:1rem">Generic Emails to Try</h4>
      <div class="job-meta" style="margin-top:.5rem">${genericHtml}</div>
    `);
  } catch (err) {
    openModal(`<p class="auth-error" style="display:block">Could not find recruiters: ${escHtml(err.message)}</p>`);
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
  const form     = document.getElementById('search-form');
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
    if (!locs.length)    { showToast('Add at least one location.', 'error'); return; }

    const btn = document.getElementById('search-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Searching…`;
    statusEl.className = 'search-status info';
    statusEl.textContent = `Searching ${sources.join(', ')} in ${locs.join(', ')}… (30–90 seconds)`;
    statusEl.classList.remove('hidden');

    try {
      const result = await api('POST', '/api/search', {
        role, locations: locs, country,
        salary_target: salary, experience_years: exp, sources,
      });
      let msg = `Found ${result.jobs_found} jobs — ${result.jobs_new} new, ${result.jobs_duplicate} duplicates.`;
      if (result.errors?.length) {
        msg += ' ⚠ ' + result.errors.map(e => `${e.source}: ${e.message}`).join('; ');
        statusEl.className = 'search-status warning';
      } else {
        statusEl.className = 'search-status success';
      }
      statusEl.textContent = msg;
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
