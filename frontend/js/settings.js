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
    document.getElementById('cfg-gmail').value     = s.gmail_address || '';
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
});
