/* ── ATS Resume Matcher ── */

async function openAtsModal(jobId) {
  openModal(`<div style="text-align:center;padding:2.5rem 1rem">
    <span class="spinner"></span>
    <p style="margin-top:1rem;color:var(--muted);font-size:.9rem">Matching your resume to this job…</p>
  </div>`);

  try {
    const data = await api('GET', `/api/ats/match/${jobId}`);

    if (data.error) {
      openModal(`<div style="padding:1.5rem">
        <h3 style="margin-bottom:.75rem">📊 ATS Match</h3>
        <p style="color:var(--muted);font-size:.9rem">${escHtml(data.error)}</p>
        <div style="margin-top:1.25rem">
          <button class="btn btn-primary" onclick="closeModal();navigate('resume')">Upload Resume →</button>
        </div>
      </div>`);
      return;
    }

    const score      = data.score || 0;
    const scoreColor = score >= 70 ? '#059669' : score >= 40 ? '#d97706' : '#e11d48';
    const scoreLabel = score >= 70 ? 'Strong Match' : score >= 40 ? 'Partial Match' : 'Weak Match';

    const matchedHtml = (data.matched || []).slice(0, 30).map(k =>
      `<span class="gap-chip" style="background:#dcfce7;color:#166534;border-color:#86efac">${escHtml(k)}</span>`
    ).join('');

    const missingHtml = (data.missing || []).slice(0, 25).map(k =>
      `<span class="gap-chip">${escHtml(k)}</span>`
    ).join('');

    openModal(`<div style="min-width:min(500px,90vw)">
      <h3 style="margin-bottom:1.25rem">📊 Resume vs Job Match</h3>

      <div style="display:flex;align-items:center;gap:1.25rem;padding:1rem;background:var(--surface-2);border-radius:var(--radius-sm);margin-bottom:1.5rem">
        <div style="font-size:3rem;font-weight:800;color:${scoreColor};line-height:1">${score}%</div>
        <div>
          <div style="font-weight:700;color:${scoreColor}">${scoreLabel}</div>
          <div style="font-size:.8rem;color:var(--muted);margin-top:.2rem">
            ${data.matched.length} of ${data.total_jd_keywords} job keywords found in your resume
          </div>
        </div>
      </div>

      ${data.matched.length ? `
      <div style="margin-bottom:1.25rem">
        <div style="font-size:.78rem;font-weight:700;color:var(--text-2);margin-bottom:.5rem;text-transform:uppercase;letter-spacing:.05em">
          ✅ In Your Resume (${data.matched.length})
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:.3rem">${matchedHtml}</div>
      </div>` : ''}

      ${data.missing.length ? `
      <div style="margin-bottom:1.25rem">
        <div style="font-size:.78rem;font-weight:700;color:var(--text-2);margin-bottom:.5rem;text-transform:uppercase;letter-spacing:.05em">
          ❌ Missing from Resume (${data.missing.length})
        </div>
        <div style="display:flex;flex-wrap:wrap;gap:.3rem">${missingHtml}</div>
      </div>` : ''}

      <p style="font-size:.78rem;color:var(--muted);padding-top:.75rem;border-top:1px solid var(--border)">
        💡 Add missing keywords naturally to your resume summary or skills section to improve ATS pass rate.
        Aim for <strong>70%+</strong> before applying.
      </p>
    </div>`);

  } catch (err) {
    openModal(`<p style="color:#dc2626;padding:1rem">⚠ ${escHtml(err.message)}</p>`);
  }
}
