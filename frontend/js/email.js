let _emailJobId = null;
let _emailType  = 'cold';   // 'cold' | 'followup' | 'outreach'
let _emailRound = 1;

// openEmailModal(jobId, 'cold')
// openEmailModal(jobId, 'followup', round)
// openEmailModal(null, 'outreach', 1, { to, subject, body, post })
async function openEmailModal(jobId, type = 'cold', round = 1, prebuilt = null) {
  _emailJobId = jobId;
  _emailType  = type;
  _emailRound = round;

  // Outreach — template already built server-side
  if (type === 'outreach' && prebuilt) {
    const post = prebuilt.post || {};
    document.getElementById('email-modal-title').textContent =
      `Outreach — ${escHtml(post.company || post.role_mentioned || 'Recruiter')}`;
    document.getElementById('email-job-info').innerHTML =
      `${platformLabel(post.source)} post by <strong>${escHtml(post.poster_name || 'Recruiter')}</strong>`;
    document.getElementById('email-to').value      = prebuilt.to || '';
    document.getElementById('email-subject').value = prebuilt.subject || '';
    document.getElementById('email-body').value    = prebuilt.body || '';
    document.getElementById('email-modal-overlay').classList.remove('hidden');
    return;
  }

  try {
    const [job, settings] = await Promise.all([
      api('GET', `/api/jobs/${jobId}`),
      api('GET', '/api/settings'),
    ]);

    const email = job.recruiter_email;
    if (!email) { showToast('No recruiter email found.', 'error'); return; }

    document.getElementById('email-modal-title').textContent =
      type === 'followup'
        ? `Follow-up ${round} — ${job.company}`
        : `Cold Email — ${job.company}`;
    document.getElementById('email-job-info').innerHTML =
      `<strong>${escHtml(job.title)}</strong> at <strong>${escHtml(job.company)}</strong>`;
    document.getElementById('email-to').value = email;

    let subject, body;
    if (type === 'followup') {
      const tmpl = buildFollowupTemplate(job, settings, round);
      subject = tmpl.subject;
      body    = tmpl.body;
    } else {
      subject = `Application — ${job.title} at ${job.company}`;
      body    = buildColdEmailTemplate(job, settings);
    }

    document.getElementById('email-subject').value = subject;
    document.getElementById('email-body').value    = body;
    document.getElementById('email-modal-overlay').classList.remove('hidden');
  } catch (err) {
    showToast(`Could not open email: ${err.message}`, 'error');
  }
}

function platformLabel(source) {
  return { linkedin_post: '💼 LinkedIn', reddit: '🤖 Reddit', twitter: '🐦 Twitter' }[source] || '🌐';
}

function buildColdEmailTemplate(job, settings) {
  const name    = settings.user_name             || 'Your Name';
  const expYrs  = settings.user_experience_years || '';
  const notice  = settings.notice_period         || '';
  const role    = settings.last_search_role || job.title || 'this role';

  const expLine = expYrs && expYrs !== '0'
    ? `I have ${expYrs} years of experience in this space`
    : `I have strong experience in this space`;

  const noticeLine = notice
    ? ` and am available with ${notice} notice period`
    : '';

  return `Hi,

Came across the ${job.title} opening at ${job.company}. ${expLine}${noticeLine}. Looking forward to hearing from you.

— ${name}`.trim();
}

function buildFollowupTemplate(job, settings, round) {
  const name    = settings.user_name || 'Your Name';
  const title   = job.title;
  const company = job.company;
  const applied = job.applied_at
    ? new Date(job.applied_at).toLocaleDateString('en-US', { month: 'long', day: 'numeric' }) : '';
  const notice  = settings.notice_period || '';

  if (round === 1) {
    return {
      subject: `Following up: ${title} at ${company}`,
      body: `Hi,

Following up on my application for the ${title} role at ${company}${applied ? ` (applied ${applied})` : ''}. Still very interested — happy to connect whenever convenient.

— ${name}`.trim()
    };
  }

  return {
    subject: `Second follow-up: ${title} at ${company}`,
    body: `Hi,

One last follow-up on the ${title} role at ${company}${notice ? `. I'm available with ${notice} notice` : ''}. If it's still open I'd love to chat, even briefly.

— ${name}`.trim()
  };
}

function closeEmailModal() {
  document.getElementById('email-modal-overlay').classList.add('hidden');
  _emailJobId = null;
}

document.addEventListener('DOMContentLoaded', () => {
  document.getElementById('email-modal-close').addEventListener('click', closeEmailModal);
  document.getElementById('email-cancel-btn').addEventListener('click', closeEmailModal);
  document.getElementById('email-modal-overlay').addEventListener('click', e => {
    if (e.target === e.currentTarget) closeEmailModal();
  });

  document.getElementById('email-form').addEventListener('submit', async e => {
    e.preventDefault();
    const btn = document.getElementById('email-send-btn');
    btn.disabled = true;
    btn.innerHTML = `<span class="spinner"></span> Sending…`;

    try {
      const payload = {
        job_id:   _emailJobId,
        to_email: document.getElementById('email-to').value,
        subject:  document.getElementById('email-subject').value,
        body:     document.getElementById('email-body').value,
      };

      if (_emailType === 'followup') {
        await api('POST', '/api/followup/send', { ...payload, followup_number: _emailRound });
      } else {
        // cold and outreach both use /api/email/send
        await api('POST', '/api/email/send', payload);
        // Mark outreach post as contacted
        if (_emailType === 'outreach' && !_emailJobId) {
          // post_id passed via prebuilt context — mark contacted on backend
        }
      }

      const successMsg = {
        followup: 'Follow-up sent!',
        outreach: 'Outreach email sent!',
        cold: 'Email sent! Job marked as applied.',
      }[_emailType] || 'Email sent!';

      showToast(successMsg, 'success');
      closeEmailModal();

      if (State.currentPage === 'jobs')     loadJobs(State.page);
      if (State.currentPage === 'tracker')  renderTracker();
      if (State.currentPage === 'followup') renderFollowups();
      if (State.currentPage === 'outreach') loadSocialPosts(OutreachState.page);
      refreshStats();
    } catch (err) {
      showToast(`Send failed: ${err.message}`, 'error');
    } finally {
      btn.disabled = false;
      btn.innerHTML = `<span class="btn-icon">✉</span> Send`;
    }
  });
});
