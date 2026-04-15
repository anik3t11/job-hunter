/* ── Resume Tab — Upload, Parse, Score ── */

const RING_R = 50;
const RING_C = 2 * Math.PI * RING_R; // ≈ 314.16

document.addEventListener('DOMContentLoaded', () => {
  const dropZone  = document.getElementById('resume-drop-zone');
  const fileInput = document.getElementById('resume-file-input');
  const resultEl  = document.getElementById('resume-parse-result');

  dropZone.addEventListener('click', () => fileInput.click());

  dropZone.addEventListener('dragover', e => {
    e.preventDefault();
    dropZone.classList.add('drag-over');
  });
  dropZone.addEventListener('dragleave', () => dropZone.classList.remove('drag-over'));
  dropZone.addEventListener('drop', e => {
    e.preventDefault();
    dropZone.classList.remove('drag-over');
    const file = e.dataTransfer.files[0];
    if (file) processResumeFile(file);
  });
  fileInput.addEventListener('change', () => {
    if (fileInput.files[0]) processResumeFile(fileInput.files[0]);
  });

  async function processResumeFile(file) {
    const ext = file.name.split('.').pop().toLowerCase();
    if (!['pdf', 'docx', 'doc'].includes(ext)) {
      showToast('Please upload a PDF or DOCX file.', 'error');
      return;
    }
    dropZone.innerHTML = `<div class="drop-icon"><span class="spinner"></span></div><p class="drop-hint">Parsing resume…</p>`;

    const targetRole = document.getElementById('resume-target-role')?.value.trim() || '';

    try {
      const formData = new FormData();
      formData.append('file', file);
      if (targetRole) formData.append('target_role', targetRole);

      const token = localStorage.getItem('jh_token');
      const headers = {};
      if (token) headers['Authorization'] = `Bearer ${token}`;

      const resp = await fetch('/api/resume/upload', { method: 'POST', body: formData, headers });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }
      const data = await resp.json();
      showParseResult(data.profile, data.score, file.name);
    } catch (err) {
      showToast(`Resume parse failed: ${err.message}`, 'error');
      resetDropZone();
    }
  }

  function showParseResult(profile, scoreData, filename) {
    dropZone.innerHTML = `
      <div class="drop-icon">✅</div>
      <p class="drop-hint"><strong>${escHtml(filename)}</strong><br/>
        <span class="drop-sub">${profile.word_count || 0} words parsed</span></p>
      <input type="file" id="resume-file-input" accept=".pdf,.docx,.doc" class="hidden" />`;
    dropZone.querySelector('input').addEventListener('change', e => {
      if (e.target.files[0]) processResumeFile(e.target.files[0]);
    });

    const skillCount = profile.skills?.length || 0;
    const titles     = profile.job_titles?.join(', ') || '—';

    resultEl.innerHTML = `
      <div class="parse-result-card">
        <h4>Extracted from Resume</h4>
        <div class="parse-grid">
          ${profile.name            ? `<div class="parse-item"><span class="parse-label">Name</span><span class="parse-val">${escHtml(profile.name)}</span></div>` : ''}
          ${profile.experience_years ? `<div class="parse-item"><span class="parse-label">Experience</span><span class="parse-val">${profile.experience_years} years</span></div>` : ''}
          ${profile.notice_period   ? `<div class="parse-item"><span class="parse-label">Notice Period</span><span class="parse-val">${escHtml(profile.notice_period)}</span></div>` : ''}
          <div class="parse-item"><span class="parse-label">Job Titles</span><span class="parse-val">${escHtml(titles)}</span></div>
          <div class="parse-item full-width"><span class="parse-label">Skills (${skillCount})</span><span class="parse-val">${escHtml((profile.skills||[]).slice(0,20).join(', '))}</span></div>
          ${profile.summary ? `<div class="parse-item full-width"><span class="parse-label">Summary</span><span class="parse-val">${escHtml(profile.summary.slice(0,200))}${profile.summary.length>200?'…':''}</span></div>` : ''}
        </div>
        <div class="parse-actions">
          <button class="btn btn-primary" id="apply-resume-btn">Apply to Profile →</button>
          <button class="btn btn-secondary" id="find-resume-jobs-btn">🔍 Find Matching Jobs</button>
          <span class="parse-hint">Pre-fills your Name, Skills, Experience &amp; Notice Period in Settings.</span>
        </div>
      </div>`;
    resultEl.classList.remove('hidden');
    document.getElementById('apply-resume-btn').addEventListener('click', () => applyProfile(profile));
    document.getElementById('find-resume-jobs-btn').addEventListener('click', () => findJobsFromResume(profile));

    // Score section
    if (scoreData) renderScoreSection(scoreData);
  }

  function renderScoreSection(scoreData) {
    const section = document.getElementById('resume-score-section');
    section.classList.remove('hidden');

    const score = scoreData.score || 0;
    const fill  = document.getElementById('score-ring-fill');
    const num   = document.getElementById('resume-score-number');

    // Animate ring
    const dashVal = (score / 100) * RING_C;
    fill.style.strokeDasharray  = `${dashVal} ${RING_C}`;
    fill.style.strokeDashoffset = '0';
    fill.style.stroke = score >= 70 ? '#059669' : score >= 40 ? '#d97706' : '#e11d48';
    num.textContent = score;
    num.style.color = score >= 70 ? '#059669' : score >= 40 ? '#d97706' : '#e11d48';

    // Breakdown bars
    const breakdown = scoreData.breakdown || {};
    const breakdownEl = document.getElementById('score-breakdown');
    breakdownEl.innerHTML = Object.entries(breakdown).map(([dim, val]) => {
      const max = getDimMax(dim);
      const pct = max ? Math.round((val / max) * 100) : 0;
      return `
        <div class="score-dim">
          <div class="score-dim-header">
            <span class="score-dim-name">${escHtml(dim)}</span>
            <span class="score-dim-val">${val}/${max}</span>
          </div>
          <div class="bar-track">
            <div class="bar-fill" style="width:${pct}%;background:${pct>=70?'#059669':pct>=40?'#d97706':'#e11d48'}"></div>
          </div>
        </div>`;
    }).join('');

    // Tips
    const tips = scoreData.tips || [];
    if (tips.length) {
      const tipsList = document.getElementById('tips-list');
      tipsList.innerHTML = tips.map(t => `<li class="tip-item">${escHtml(t)}</li>`).join('');
      document.getElementById('resume-tips').classList.remove('hidden');
    }

    section.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }

  function getDimMax(dim) {
    const maxMap = {
      'Contact Info': 10, 'Resume Length': 10, 'Experience': 25,
      'Skills Match': 20, 'Summary': 15, 'Education': 10,
      'Notice Period': 5, 'Format': 5,
    };
    return maxMap[dim] || 10;
  }

  async function applyProfile(profile) {
    // Navigate to settings first
    location.hash = 'settings';
    await new Promise(r => setTimeout(r, 150)); // wait for render

    if (profile.name)             document.getElementById('cfg-name').value   = profile.name;
    if (profile.experience_years) document.getElementById('cfg-exp').value    = profile.experience_years;
    if (profile.notice_period)    document.getElementById('cfg-notice').value = profile.notice_period;
    if (profile.skills_str)       document.getElementById('cfg-skills').value = profile.skills_str;
    if (profile.summary)          document.getElementById('cfg-resume').value = profile.summary;

    try {
      const payload = {};
      if (profile.name)             payload.user_name = profile.name;
      if (profile.experience_years) payload.user_experience_years = String(profile.experience_years);
      if (profile.notice_period)    payload.notice_period = profile.notice_period;
      if (profile.skills_str)       payload.user_skills = profile.skills_str;
      if (profile.summary)          payload.resume_summary = profile.summary;
      if (profile.raw_text)         payload.resume_text = profile.raw_text.slice(0, 4000);
      await api('POST', '/api/resume/save', payload);
      showToast('Profile updated from resume!', 'success');
    } catch (err) {
      showToast(`Could not save profile: ${err.message}`, 'error');
    }
  }

  async function findJobsFromResume(profile) {
    // First apply the profile
    await applyProfile(profile);
    // Navigate to jobs tab
    location.hash = 'jobs';
    await new Promise(r => setTimeout(r, 200));
    // Pre-fill the search role with top job title from resume
    const role = profile.job_titles?.[0] || profile.target_role || '';
    if (role) {
      const roleInput = document.getElementById('search-role');
      if (roleInput) roleInput.value = role;
    }
    showToast('Profile applied! Set your location and click Search.', 'success');
  }

  function resetDropZone() {
    dropZone.innerHTML = `
      <div class="drop-icon">📄</div>
      <p class="drop-hint">Drag &amp; drop your resume here<br/><span class="drop-sub">or click to browse</span></p>
      <input type="file" id="resume-file-input" accept=".pdf,.docx,.doc" class="hidden" />`;
    dropZone.querySelector('input').addEventListener('change', e => {
      if (e.target.files[0]) processResumeFile(e.target.files[0]);
    });
  }
});
