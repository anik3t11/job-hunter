/* ── AI Features — Cover Letter & Resume Tailoring ── */

let _aiStatus = null;

async function fetchAiStatus() {
  try {
    _aiStatus = await api('GET', '/api/ai/status');
  } catch (_) {
    _aiStatus = { available: false, remaining: 0 };
  }
}

/* Called on app load and after each AI use */
async function refreshAiCredits() {
  await fetchAiStatus();
  const badge = document.getElementById('ai-credits-badge');
  if (!badge) return;
  if (!_aiStatus || !_aiStatus.available) {
    badge.textContent = 'AI: no key';
    badge.className = 'ai-credits-badge unavailable';
  } else if (_aiStatus.has_own_key) {
    badge.textContent = '✨ AI: ∞';
    badge.className = 'ai-credits-badge unlimited';
  } else {
    badge.textContent = `✨ AI: ${_aiStatus.remaining}/${_aiStatus.daily_limit} left`;
    badge.className = `ai-credits-badge ${_aiStatus.remaining > 0 ? 'ok' : 'empty'}`;
  }
}

async function openAiModal(jobId, mode) {
  if (!_aiStatus) await fetchAiStatus();

  const isAvailable = _aiStatus && _aiStatus.available;
  const hasCredits  = isAvailable && (_aiStatus.has_own_key || _aiStatus.remaining > 0);
  const modeLabel   = mode === 'cover' ? 'Cover Letter' : 'Tailored Resume';
  const modeIcon    = mode === 'cover' ? '✨' : '📝';

  if (!isAvailable) {
    openModal(`
      <div class="ai-modal">
        <div class="ai-modal-header">
          <span class="ai-modal-icon">🤖</span>
          <h3>AI Features Not Available</h3>
        </div>
        <p style="color:var(--muted);margin:1rem 0">No AI API key is configured on this server yet.</p>
        <p>To enable AI features, add your own <strong>Gemini</strong> or <strong>Groq</strong> API key in
          <a href="#" onclick="closeModal();navigate('settings')">Settings → AI Keys</a>
          (both are free).</p>
        <div class="ai-modal-actions">
          <a href="https://aistudio.google.com/apikey" target="_blank" class="btn btn-primary">Get Free Gemini Key ↗</a>
          <a href="https://console.groq.com/keys" target="_blank" class="btn btn-ghost">Get Free Groq Key ↗</a>
        </div>
      </div>
    `);
    return;
  }

  if (!hasCredits) {
    openModal(`
      <div class="ai-modal">
        <div class="ai-modal-header">
          <span class="ai-modal-icon">⏰</span>
          <h3>Daily AI Limit Reached</h3>
        </div>
        <p style="color:var(--muted);margin:1rem 0">
          You've used all ${_aiStatus.daily_limit} free AI credits for today.
          They reset at midnight.
        </p>
        <p>For unlimited access, add your own free API key in
          <a href="#" onclick="closeModal();navigate('settings')">Settings → AI Keys</a>.</p>
        <div class="ai-modal-actions">
          <a href="https://aistudio.google.com/apikey" target="_blank" class="btn btn-primary">Get Free Gemini Key ↗</a>
          <button class="btn btn-ghost" onclick="closeModal()">Close</button>
        </div>
      </div>
    `);
    return;
  }

  // Show generation UI
  openModal(`
    <div class="ai-modal" id="ai-modal-content">
      <div class="ai-modal-header">
        <span class="ai-modal-icon">${modeIcon}</span>
        <h3>Generate ${modeLabel}</h3>
        <span class="ai-credits-inline">${_aiStatus.has_own_key ? '∞ own key' : `${_aiStatus.remaining} credits left`}</span>
      </div>
      <div class="ai-generating" id="ai-spinner">
        <span class="spinner"></span>
        <p>Generating ${modeLabel.toLowerCase()}… (5–15 seconds)</p>
      </div>
      <div class="ai-result hidden" id="ai-result-section">
        <div class="ai-result-toolbar">
          <button class="btn btn-sm btn-ghost" onclick="copyAiResult()">📋 Copy</button>
          <button class="btn btn-sm btn-ghost" onclick="regenerateAi(${jobId},'${mode}')">🔄 Regenerate</button>
        </div>
        <textarea class="ai-result-text" id="ai-result-text" rows="16" readonly></textarea>
      </div>
    </div>
  `);

  await runAiGeneration(jobId, mode);
}

async function runAiGeneration(jobId, mode) {
  const endpoint = mode === 'cover' ? '/api/ai/cover-letter' : '/api/ai/tailor-resume';
  try {
    const data = await api('POST', endpoint, { job_id: jobId });
    document.getElementById('ai-spinner').classList.add('hidden');
    const resultSection = document.getElementById('ai-result-section');
    if (resultSection) {
      resultSection.classList.remove('hidden');
      document.getElementById('ai-result-text').value = data.text;
    }
    // Refresh credit count
    if (_aiStatus && !_aiStatus.has_own_key) {
      _aiStatus.remaining = Math.max(0, _aiStatus.remaining - 1);
      refreshAiCredits();
    }
  } catch (err) {
    const spinner = document.getElementById('ai-spinner');
    if (spinner) {
      spinner.innerHTML = `<div class="ai-error">
        <p>⚠ ${escHtml(err.message)}</p>
        <button class="btn btn-ghost" onclick="closeModal()">Close</button>
      </div>`;
    }
  }
}

async function regenerateAi(jobId, mode) {
  document.getElementById('ai-result-section').classList.add('hidden');
  document.getElementById('ai-spinner').classList.remove('hidden');
  document.getElementById('ai-spinner').innerHTML = `
    <span class="spinner"></span>
    <p>Regenerating… (5–15 seconds)</p>`;
  await runAiGeneration(jobId, mode);
}

function copyAiResult() {
  const txt = document.getElementById('ai-result-text');
  if (!txt) return;
  navigator.clipboard.writeText(txt.value).then(() => {
    showToast('Copied to clipboard!', 'success');
  }).catch(() => {
    txt.select();
    document.execCommand('copy');
    showToast('Copied!', 'success');
  });
}

document.addEventListener('DOMContentLoaded', () => {
  refreshAiCredits();
});
