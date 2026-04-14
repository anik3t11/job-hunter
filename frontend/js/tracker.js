const COLUMNS = [
  { key: 'new',       label: 'New',       cls: 'col-new'       },
  { key: 'reviewed',  label: 'Reviewed',  cls: 'col-reviewed'  },
  { key: 'applied',   label: 'Applied',   cls: 'col-applied'   },
  { key: 'interview', label: 'Interview', cls: 'col-interview' },
];
const NEXT = { new:'reviewed', reviewed:'applied', applied:'interview', interview:null };
const PREV = { new:null, reviewed:'new', applied:'reviewed', interview:'applied' };

async function renderTracker() {
  const board = document.getElementById('kanban-board');
  board.innerHTML = '<div style="padding:2rem;color:var(--muted)">Loading…</div>';
  try {
    const data = await api('GET', '/api/jobs?per_page=200&sort=date');
    const grouped = {};
    COLUMNS.forEach(c => { grouped[c.key] = []; });
    data.jobs.forEach(j => { if (grouped[j.status]) grouped[j.status].push(j); });

    board.innerHTML = COLUMNS.map(col => `
      <div class="kanban-col ${col.cls}">
        <div class="kanban-col-header">
          <span class="col-title">${col.label}</span>
          <span class="col-count">${grouped[col.key].length}</span>
        </div>
        <div id="col-cards-${col.key}">
          ${grouped[col.key].length
            ? grouped[col.key].map(miniCard).join('')
            : '<div style="font-size:.78rem;color:var(--muted);text-align:center;padding:1.5rem 0">Empty</div>'
          }
        </div>
      </div>`).join('');

    board.querySelectorAll('.move-next').forEach(b => b.addEventListener('click', async e => {
      e.stopPropagation();
      const nxt = NEXT[b.dataset.current];
      if (nxt) { await updateJobStatus(+b.dataset.id, nxt); renderTracker(); }
    }));
    board.querySelectorAll('.move-prev').forEach(b => b.addEventListener('click', async e => {
      e.stopPropagation();
      const prv = PREV[b.dataset.current];
      if (prv) { await updateJobStatus(+b.dataset.id, prv); renderTracker(); }
    }));
    board.querySelectorAll('.mini-card').forEach(c =>
      c.addEventListener('click', () => openJobDetail(+c.dataset.id)));
  } catch (err) {
    board.innerHTML = `<div style="color:var(--danger)">Error: ${err.message}</div>`;
  }
}

function miniCard(job) {
  const salary = formatSalary(job.salary_min, job.salary_max, job.salary_raw);
  const nxt = NEXT[job.status];
  const prv = PREV[job.status];
  const hot = job.is_hot ? '🔥 ' : '';
  return `
    <div class="mini-card" data-id="${job.id}">
      <div class="mini-title">${hot}${escHtml(job.title)}</div>
      <div class="mini-company">${escHtml(job.company)}</div>
      ${salary ? `<div class="mini-company" style="margin-top:.15rem">${salary}</div>` : ''}
      <div class="mini-footer">
        ${scorePill(job.match_score)}
        <div style="display:flex;gap:.25rem">
          ${prv ? `<button class="btn btn-sm btn-ghost move-prev" data-id="${job.id}" data-current="${job.status}">← ${prv}</button>` : ''}
          ${nxt ? `<button class="btn btn-sm btn-primary move-next" data-id="${job.id}" data-current="${job.status}">${nxt} →</button>` : '<span style="font-size:.75rem">🏆</span>'}
        </div>
      </div>
    </div>`;
}
