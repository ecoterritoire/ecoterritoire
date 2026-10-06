let token = sessionStorage.getItem('admin_token');

const $ = (selector) => document.querySelector(selector);

const formatDate = (value) =>
  value ? new Date(value).toLocaleString('fr-FR') : 'Jamais';

async function request(path, options = {}) {
  const response = await fetch(`/admin${path}`, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers || {}),
    },
  });
  const body = await response.json().catch(() => ({}));
  if (response.status === 401 && token && path !== '/login') {
    sessionStorage.removeItem('admin_token');
    token = null;
    $('#dashboard').hidden = true;
    $('#login').hidden = false;
  }
  if (!response.ok) throw new Error(body.detail || 'Erreur API');
  return body;
}

async function loadDashboard() {
  const [stats, tokens] = await Promise.all([
    request('/stats'),
    request('/tokens?limit=200'),
  ]);

  $('#stats').innerHTML = [
    ['Clés totales', stats.total_tokens],
    ['Clés actives', stats.active_tokens],
    ['Utilisations', stats.total_usage],
    ['Créées (7 jours)', stats.created_last_7_days],
    ['Utilisées (24 heures)', stats.used_last_24_hours],
  ].map(([label, value]) => `
    <article class="card stat"><span>${label}</span><strong>${value}</strong></article>
  `).join('');

  $('#tokens').innerHTML = tokens.data.map((item) => `
    <tr>
      <td>${item.description || '-'}</td>
      <td>${formatDate(item.created_at)}</td>
      <td>${formatDate(item.last_used_at)}</td>
      <td>${item.usage_count}</td>
      <td>${item.is_active ? 'Active' : 'Inactive'}</td>
    </tr>
  `).join('');
}

function showView(view) {
  document.querySelectorAll('.view').forEach((element) => {
    element.hidden = element.id !== `${view}-view`;
  });
  document.querySelectorAll('.tab').forEach((element) => {
    element.classList.toggle('active', element.dataset.view === view);
  });
  if (view === 'keys') loadDashboard().catch((error) => { $('#error').textContent = error.message; });
}

async function showDashboard() {
  $('#login').hidden = true;
  $('#dashboard').hidden = false;
  try {
    await loadDashboard();
    $('#error').textContent = '';
  } catch (error) {
    $('#error').textContent = error.message;
  }
}

$('#login-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  try {
    const body = await request('/login', {
      method: 'POST',
      body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))),
    });
    token = body.token;
    sessionStorage.setItem('admin_token', token);
    await showDashboard();
  } catch (error) {
    $('#error').textContent = error.message;
  }
});

document.querySelectorAll('.tab').forEach((tab) => {
  tab.addEventListener('click', () => showView(tab.dataset.view));
});
$('#refresh-overview').addEventListener('click', loadDashboard);
$('#refresh-keys').addEventListener('click', loadDashboard);
$('#create-key-form').addEventListener('submit', async (event) => {
  event.preventDefault();
  $('#create-error').textContent = '';
  try {
    const body = await request('/api-keys', {
      method: 'POST',
      body: JSON.stringify(Object.fromEntries(new FormData(event.currentTarget))),
    });
    $('#created-key-value').textContent = body.token;
    $('#created-key').hidden = false;
    event.currentTarget.reset();
    await loadDashboard();
  } catch (error) {
    $('#create-error').textContent = error.message;
  }
});
$('#copy-key').addEventListener('click', async () => {
  await navigator.clipboard.writeText($('#created-key-value').textContent);
});
$('#logout').addEventListener('click', () => {
  request('/logout', { method: 'POST' }).catch(() => {});
  sessionStorage.removeItem('admin_token');
  token = null;
  $('#dashboard').hidden = true;
  $('#login').hidden = false;
});

if (token) showDashboard();
