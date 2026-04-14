/* ── Analytics Tab ── */

async function loadAnalytics() {
  try {
    const d = await api('GET', '/api/analytics');
    // Stat cards
    document.getElementById('a-total').textContent      = d.total_jobs ?? '—';
    document.getElementById('a-applied').textContent    = d.applied ?? '—';
    document.getElementById('a-interviews').textContent = d.interviews ?? '—';
    document.getElementById('a-offers').textContent     = d.offers ?? '—';
    document.getElementById('a-response').textContent   = d.response_rate
      ? `${Math.round(d.response_rate * 100)}%` : '—';

    // By source bar chart
    renderBarChart('a-by-source', d.by_source || {});

    // Score distribution
    renderBarChart('a-score-dist', d.score_distribution || {});

    // Skill gaps
    renderSkillGaps(d.top_skill_gaps || []);

  } catch (err) {
    showToast(`Analytics error: ${err.message}`, 'error');
  }
}

function renderBarChart(elId, data) {
  const el = document.getElementById(elId);
  const entries = Object.entries(data);
  if (!entries.length) {
    el.innerHTML = `<p class="empty-chart">No data yet.</p>`;
    return;
  }
  const max = Math.max(...entries.map(([,v]) => v), 1);
  el.innerHTML = entries.map(([label, count]) => {
    const pct = Math.round((count / max) * 100);
    return `
      <div class="bar-row">
        <span class="bar-label">${escHtml(String(label))}</span>
        <div class="bar-track">
          <div class="bar-fill" style="width:${pct}%"></div>
        </div>
        <span class="bar-count">${count}</span>
      </div>`;
  }).join('');
}

function renderSkillGaps(gaps) {
  const el = document.getElementById('a-skill-gaps');
  if (!gaps.length) {
    el.innerHTML = `<p class="empty-chart">No skill gap data yet — run a job search first.</p>`;
    return;
  }
  const max = gaps[0][1] || 1;
  el.innerHTML = gaps.slice(0, 15).map(([skill, count]) => {
    const pct = Math.round((count / max) * 100);
    return `
      <div class="gap-row">
        <span class="gap-skill">${escHtml(skill)}</span>
        <div class="bar-track" style="flex:1">
          <div class="bar-fill bar-fill-gap" style="width:${pct}%"></div>
        </div>
        <span class="bar-count">${count} jobs</span>
      </div>`;
  }).join('');
}

document.addEventListener('DOMContentLoaded', () => {
  const btn = document.getElementById('analytics-refresh-btn');
  if (btn) btn.addEventListener('click', loadAnalytics);
});
