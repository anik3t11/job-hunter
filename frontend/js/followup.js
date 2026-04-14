async function renderFollowups() {
  const container = document.getElementById('followup-list');
  container.innerHTML = '<div style="padding:2rem;color:var(--muted)">Loading…</div>';
  try {
    const data = await api('GET', '/api/followup');
    const list = data.followups || [];
    if (!list.length) {
      container.innerHTML = `
        <div class="empty-state">
          <div class="empty-icon">✅</div>
          <p>No follow-ups due. You're all caught up!</p>
        </div>`;
      return;
    }
    container.innerHTML = list.map(followupCard).join('');
    container.querySelectorAll('.fu-send-btn').forEach(b => {
      b.addEventListener('click', () => openEmailModal(+b.dataset.id, 'followup', +b.dataset.round));
    });
    container.querySelectorAll('.fu-dismiss-btn').forEach(b => {
      b.addEventListener('click', async () => {
        await api('POST', `/api/followup/${b.dataset.id}/dismiss`);
        showToast('Follow-up dismissed.', 'info');
        renderFollowups();
        refreshStats();
      });
    });
  } catch (err) {
    container.innerHTML = `<div style="color:var(--danger)">Error: ${err.message}</div>`;
  }
}

function followupCard(item) {
  const round = item.followup_1_at ? 2 : 1;
  const applied = item.applied_at ? new Date(item.applied_at).toLocaleDateString() : '—';
  const due = item.followup_due_at ? new Date(item.followup_due_at).toLocaleDateString() : '—';
  const hasEmail = !!item.recruiter_email;

  return `
    <div class="followup-card">
      <div class="followup-info">
        <div class="followup-title">
          ${escHtml(item.title)} <span style="font-weight:400;color:var(--muted)">@</span> ${escHtml(item.company)}
        </div>
        <div class="followup-meta">
          Applied: ${applied} · Due: ${due}
          ${item.recruiter_email ? `· 📧 <a href="mailto:${escAttr(item.recruiter_email)}">${escHtml(item.recruiter_email)}</a>` : '· No email found'}
        </div>
      </div>
      <div class="followup-actions">
        <span class="followup-round r${round}">Follow-up ${round}</span>
        ${hasEmail
          ? `<button class="btn btn-sm btn-primary fu-send-btn" data-id="${item.id}" data-round="${round}">✉ Send</button>`
          : `<button class="btn btn-sm btn-secondary" disabled title="No recruiter email">No Email</button>`
        }
        <button class="btn btn-sm btn-ghost fu-dismiss-btn" data-id="${item.id}">Dismiss</button>
      </div>
    </div>`;
}
