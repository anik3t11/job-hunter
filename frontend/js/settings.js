async function loadSettings() {
  try {
    const s = await api('GET', '/api/settings');
    document.getElementById('cfg-name').value      = s.user_name || '';
    document.getElementById('cfg-exp').value       = s.user_experience_years || '';
    document.getElementById('cfg-skills').value    = s.user_skills || '';
    document.getElementById('cfg-locations').value = s.user_preferred_locations || '';
    document.getElementById('cfg-salary').value    = s.user_salary_target || s.user_salary_min || '';
    document.getElementById('cfg-notice').value    = s.notice_period || '';
    document.getElementById('cfg-resume').value    = s.resume_summary || '';
    document.getElementById('cfg-gmail').value       = s.gmail_address || '';
    // Show masked key placeholder if key exists
    if (s.gemini_api_key) document.getElementById('cfg-gemini-key').placeholder = '••••••••••• (saved)';
    if (s.groq_api_key)   document.getElementById('cfg-groq-key').placeholder   = '••••••••••• (saved)';
  } catch (err) {
    showToast(`Could not load settings: ${err.message}`, 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('settings-form').addEventListener('submit', async e => {
    e.preventDefault();
    const payload = {
      user_name:                document.getElementById('cfg-name').value.trim(),
      user_experience_years:    document.getElementById('cfg-exp').value,
      notice_period:            document.getElementById('cfg-notice').value.trim(),
      user_skills:              document.getElementById('cfg-skills').value.trim(),
      user_preferred_locations: document.getElementById('cfg-locations').value.trim(),
      user_salary_target:       document.getElementById('cfg-salary').value,
      resume_summary:           document.getElementById('cfg-resume').value.trim(),
      gmail_address:            document.getElementById('cfg-gmail').value.trim(),
    };
    const pwd = document.getElementById('cfg-password').value;
    if (pwd) payload.gmail_app_password = pwd;

    try {
      await api('POST', '/api/settings', payload);
      showToast('Settings saved!', 'success');
      document.getElementById('cfg-password').value = '';
    } catch (err) {
      showToast(`Save failed: ${err.message}`, 'error');
    }
  });

  document.getElementById('test-email-btn').addEventListener('click', async () => {
    const el = document.getElementById('email-test-result');
    el.textContent = 'Testing…';
    el.className = 'test-result';
    try {
      const res = await api('POST', '/api/email/test');
      el.textContent = res.ok ? `✓ ${res.message}` : `✗ ${res.message}`;
      el.className   = `test-result ${res.ok ? 'ok' : 'err'}`;
    } catch (err) {
      el.textContent = `✗ ${err.message}`;
      el.className   = 'test-result err';
    }
  });

  /* Save AI Keys */
  document.getElementById('save-ai-keys-btn').addEventListener('click', async () => {
    const geminiKey = document.getElementById('cfg-gemini-key').value.trim();
    const groqKey   = document.getElementById('cfg-groq-key').value.trim();
    const statusEl  = document.getElementById('ai-keys-status');

    if (!geminiKey && !groqKey) {
      statusEl.textContent = 'Enter at least one key.';
      statusEl.className = 'test-result err';
      return;
    }

    const btn = document.getElementById('save-ai-keys-btn');
    btn.disabled = true; btn.textContent = 'Saving…';
    statusEl.textContent = ''; statusEl.className = 'test-result';

    try {
      const payload = {};
      if (geminiKey) payload.gemini_api_key = geminiKey;
      if (groqKey)   payload.groq_api_key   = groqKey;
      await api('POST', '/api/settings', payload);
      statusEl.textContent = '✓ Keys saved!';
      statusEl.className = 'test-result ok';
      document.getElementById('cfg-gemini-key').value = '';
      document.getElementById('cfg-groq-key').value   = '';
      if (geminiKey) document.getElementById('cfg-gemini-key').placeholder = '••••••••••• (saved)';
      if (groqKey)   document.getElementById('cfg-groq-key').placeholder   = '••••••••••• (saved)';
      if (typeof refreshAiCredits === 'function') refreshAiCredits();
    } catch (err) {
      statusEl.textContent = `✗ ${err.message}`;
      statusEl.className = 'test-result err';
    } finally {
      btn.disabled = false; btn.textContent = 'Save AI Keys';
    }
  });

  /* Change Password */
  document.getElementById('change-pwd-btn').addEventListener('click', async () => {
    const current = document.getElementById('pwd-current').value;
    const newPwd  = document.getElementById('pwd-new').value;
    const confirm = document.getElementById('pwd-confirm').value;
    const errEl   = document.getElementById('pwd-error');
    errEl.classList.add('hidden');

    if (!current || !newPwd || !confirm) {
      errEl.textContent = 'All fields are required.'; errEl.classList.remove('hidden'); return;
    }
    if (newPwd.length < 6) {
      errEl.textContent = 'New password must be at least 6 characters.'; errEl.classList.remove('hidden'); return;
    }
    if (newPwd !== confirm) {
      errEl.textContent = 'New passwords do not match.'; errEl.classList.remove('hidden'); return;
    }
    const btn = document.getElementById('change-pwd-btn');
    btn.disabled = true; btn.textContent = 'Updating…';
    try {
      await api('POST', '/api/auth/change-password', { current_password: current, new_password: newPwd });
      showToast('Password updated successfully!', 'success');
      document.getElementById('pwd-current').value = '';
      document.getElementById('pwd-new').value = '';
      document.getElementById('pwd-confirm').value = '';
    } catch (err) {
      errEl.textContent = err.message; errEl.classList.remove('hidden');
    } finally {
      btn.disabled = false; btn.textContent = 'Update Password';
    }
  });
});
