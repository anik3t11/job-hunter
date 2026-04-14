/* ── Resume Upload & Auto-fill ── */

document.addEventListener('DOMContentLoaded', () => {
  const dropZone  = document.getElementById('resume-drop-zone');
  const fileInput = document.getElementById('resume-file-input');
  const resultEl  = document.getElementById('resume-parse-result');

  // Click to browse
  dropZone.addEventListener('click', () => fileInput.click());

  // Drag & drop
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

    // Show loading state
    dropZone.innerHTML = `<div class="drop-icon"><span class="spinner"></span></div>
      <p class="drop-hint">Parsing resume…</p>`;

    try {
      const formData = new FormData();
      formData.append('file', file);

      const resp = await fetch('/api/resume/upload', { method: 'POST', body: formData });
      if (!resp.ok) {
        const err = await resp.json().catch(() => ({ detail: 'Upload failed' }));
        throw new Error(err.detail || 'Upload failed');
      }
      const data = await resp.json();
      showParseResult(data.profile, file.name);
    } catch (err) {
      showToast(`Resume parse failed: ${err.message}`, 'error');
      resetDropZone();
    }
  }

  function showParseResult(profile, filename) {
    // Reset drop zone to show filename
    dropZone.innerHTML = `
      <div class="drop-icon">✅</div>
      <p class="drop-hint"><strong>${escHtml(filename)}</strong><br/>
        <span class="drop-sub">${profile.word_count} words parsed</span></p>
      <input type="file" id="resume-file-input" accept=".pdf,.docx,.doc" class="hidden" />`;
    dropZone.querySelector('input').addEventListener('change', e => {
      if (e.target.files[0]) processResumeFile(e.target.files[0]);
    });

    const skillCount = profile.skills?.length || 0;
    const titles = profile.job_titles?.join(', ') || '—';

    resultEl.innerHTML = `
      <div class="parse-result-card">
        <h4>Extracted from Resume</h4>
        <div class="parse-grid">
          ${profile.name ? `<div class="parse-item"><span class="parse-label">Name</span><span class="parse-val">${escHtml(profile.name)}</span></div>` : ''}
          ${profile.experience_years ? `<div class="parse-item"><span class="parse-label">Experience</span><span class="parse-val">${profile.experience_years} years</span></div>` : ''}
          ${profile.notice_period ? `<div class="parse-item"><span class="parse-label">Notice Period</span><span class="parse-val">${escHtml(profile.notice_period)}</span></div>` : ''}
          <div class="parse-item"><span class="parse-label">Job Titles Found</span><span class="parse-val">${escHtml(titles)}</span></div>
          <div class="parse-item full-width"><span class="parse-label">Skills (${skillCount})</span><span class="parse-val">${escHtml((profile.skills || []).slice(0, 20).join(', '))}</span></div>
          ${profile.summary ? `<div class="parse-item full-width"><span class="parse-label">Summary</span><span class="parse-val">${escHtml(profile.summary.slice(0, 200))}${profile.summary.length > 200 ? '…' : ''}</span></div>` : ''}
        </div>
        <div class="parse-actions">
          <button class="btn btn-primary" id="apply-resume-btn">Apply to Profile ↓</button>
          <span class="parse-hint">This will pre-fill your Name, Skills, Experience, and Notice Period below.</span>
        </div>
      </div>`;
    resultEl.classList.remove('hidden');

    document.getElementById('apply-resume-btn').addEventListener('click', () => applyProfile(profile));
  }

  async function applyProfile(profile) {
    // Fill form fields
    if (profile.name)            document.getElementById('cfg-name').value = profile.name;
    if (profile.experience_years) document.getElementById('cfg-exp').value = profile.experience_years;
    if (profile.notice_period)   document.getElementById('cfg-notice').value = profile.notice_period;
    if (profile.skills_str)      document.getElementById('cfg-skills').value = profile.skills_str;
    if (profile.summary)         document.getElementById('cfg-resume').value = profile.summary;

    // Save to backend
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

      // Scroll to profile form
      document.getElementById('cfg-name').closest('.settings-panel').scrollIntoView({ behavior: 'smooth' });
    } catch (err) {
      showToast(`Could not save profile: ${err.message}`, 'error');
    }
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
