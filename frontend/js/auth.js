/* ── Auth — token management + login/signup overlay ── */

function getToken()      { return localStorage.getItem('jh_token'); }
function setToken(t)     { localStorage.setItem('jh_token', t); }
function clearToken()    { localStorage.removeItem('jh_token'); }

function showApp(user) {
  document.getElementById('auth-overlay').classList.add('hidden');
  document.getElementById('app').classList.remove('hidden');
  const displayName = user.name || user.email || 'User';
  document.getElementById('user-name-display').textContent = displayName;
  document.getElementById('user-avatar').textContent = displayName[0].toUpperCase();
  // Admin panel
  if (user.is_admin) {
    document.getElementById('admin-panel').classList.remove('hidden');
    loadWhitelist();
  } else {
    document.getElementById('admin-panel').classList.add('hidden');
  }
}

function showAuthOverlay() {
  document.getElementById('auth-overlay').classList.remove('hidden');
  document.getElementById('app').classList.add('hidden');
}

/* ── Bootstrap on load ── */
document.addEventListener('DOMContentLoaded', async () => {
  const token = getToken();
  if (!token) { showAuthOverlay(); return; }
  try {
    const me = await api('GET', '/api/auth/me');
    showApp(me);
  } catch (_) {
    clearToken();
    showAuthOverlay();
  }

  /* Toggle login / signup */
  document.getElementById('to-signup').addEventListener('click', e => {
    e.preventDefault();
    document.getElementById('auth-login').classList.remove('active');
    document.getElementById('auth-signup').classList.add('active');
  });
  document.getElementById('to-login').addEventListener('click', e => {
    e.preventDefault();
    document.getElementById('auth-signup').classList.remove('active');
    document.getElementById('auth-login').classList.add('active');
  });

  /* Login */
  document.getElementById('login-btn').addEventListener('click', async () => {
    const email = document.getElementById('login-email').value.trim();
    const password = document.getElementById('login-password').value;
    const errEl = document.getElementById('login-error');
    errEl.classList.add('hidden');
    if (!email || !password) { errEl.textContent = 'Email and password are required.'; errEl.classList.remove('hidden'); return; }
    const btn = document.getElementById('login-btn');
    btn.disabled = true; btn.textContent = 'Signing in…';
    try {
      const res = await fetch('/api/auth/login', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ email, password }),
      });
      const data = await res.json();
      if (!res.ok) { errEl.textContent = data.detail || 'Login failed.'; errEl.classList.remove('hidden'); return; }
      setToken(data.token);
      showApp(data.user);
    } catch (_) {
      errEl.textContent = 'Network error. Please try again.';
      errEl.classList.remove('hidden');
    } finally {
      btn.disabled = false; btn.textContent = 'Sign In';
    }
  });

  /* Allow Enter key on login fields */
  ['login-email', 'login-password'].forEach(id => {
    document.getElementById(id).addEventListener('keydown', e => {
      if (e.key === 'Enter') document.getElementById('login-btn').click();
    });
  });

  /* Signup */
  document.getElementById('signup-btn').addEventListener('click', async () => {
    const name  = document.getElementById('signup-name').value.trim();
    const email = document.getElementById('signup-email').value.trim();
    const password = document.getElementById('signup-password').value;
    const errEl = document.getElementById('signup-error');
    errEl.classList.add('hidden');
    if (!email || !password) { errEl.textContent = 'Email and password are required.'; errEl.classList.remove('hidden'); return; }
    const btn = document.getElementById('signup-btn');
    btn.disabled = true; btn.textContent = 'Creating…';
    try {
      const res = await fetch('/api/auth/signup', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name, email, password }),
      });
      const data = await res.json();
      if (!res.ok) { errEl.textContent = data.detail || 'Signup failed.'; errEl.classList.remove('hidden'); return; }
      setToken(data.token);
      showApp(data.user);
    } catch (_) {
      errEl.textContent = 'Network error. Please try again.';
      errEl.classList.remove('hidden');
    } finally {
      btn.disabled = false; btn.textContent = 'Create Account';
    }
  });

  /* Logout */
  document.getElementById('logout-btn').addEventListener('click', () => {
    clearToken();
    showAuthOverlay();
  });
});

/* ── Admin whitelist management ── */
async function loadWhitelist() {
  try {
    const data = await api('GET', '/api/auth/admin/whitelist');
    const tbody = document.getElementById('admin-whitelist-body');
    if (!data.whitelist || !data.whitelist.length) {
      tbody.innerHTML = `<tr><td colspan="4" style="text-align:center;color:var(--muted)">No emails whitelisted yet.</td></tr>`;
      return;
    }
    tbody.innerHTML = data.whitelist.map(entry => `
      <tr>
        <td>${escHtml(entry.email)}</td>
        <td><span class="status-badge ${entry.used ? 'status-used' : 'status-pending'}">${entry.used ? 'Registered' : 'Pending'}</span></td>
        <td>${entry.added_at ? new Date(entry.added_at).toLocaleDateString() : '—'}</td>
        <td>
          <button class="btn btn-sm btn-ghost" onclick="removeWhitelist('${escAttr(entry.email)}')">Remove</button>
        </td>
      </tr>`).join('');
  } catch (err) {
    showToast(`Could not load whitelist: ${err.message}`, 'error');
  }
}

async function removeWhitelist(email) {
  if (!confirm(`Remove ${email} from whitelist?`)) return;
  try {
    await api('DELETE', `/api/auth/admin/whitelist/${encodeURIComponent(email)}`);
    showToast(`${email} removed.`, 'info');
    loadWhitelist();
  } catch (err) {
    showToast(err.message, 'error');
  }
}

document.addEventListener('DOMContentLoaded', () => {
  const addBtn = document.getElementById('admin-add-btn');
  if (!addBtn) return;
  addBtn.addEventListener('click', async () => {
    const email = document.getElementById('admin-invite-email').value.trim();
    const errEl = document.getElementById('admin-invite-error');
    errEl.classList.add('hidden');
    if (!email) return;
    try {
      await api('POST', '/api/auth/admin/whitelist', { email });
      showToast(`${email} added to whitelist.`, 'success');
      document.getElementById('admin-invite-email').value = '';
      loadWhitelist();
    } catch (err) {
      errEl.textContent = err.message;
      errEl.classList.remove('hidden');
    }
  });
});
