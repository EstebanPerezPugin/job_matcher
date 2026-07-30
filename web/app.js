// State management
let state = {
  jobs: [],
  applied: [],
  profile: {},
  activeTab: 'tab-available',
  searchQuery: '',
  minScoreFilter: 0,
  recentFilter: 'all',
  locationFilter: 'all',
  isRefreshing: false
};

// DOM Elements
document.addEventListener('DOMContentLoaded', async () => {
  initNavigation();
  initEventListeners();
  await loadAllData();
  renderAll();
});

// Load JSON data from relative paths or LocalStorage
async function loadAllData() {
  try {
    const localApplied = localStorage.getItem('jobagent_applied');
    const localJobs = localStorage.getItem('jobagent_jobs');
    const localProfile = localStorage.getItem('jobagent_profile');

    if (localApplied && localJobs && localProfile) {
      state.applied = JSON.parse(localApplied);
      state.jobs = JSON.parse(localJobs);
      state.profile = JSON.parse(localProfile);
    } else {
      const [resJobs, resApplied, resProfile] = await Promise.all([
        fetch('/data/jobs.json').then(r => r.json()).catch(() => []),
        fetch('/data/applied.json').then(r => r.json()).catch(() => []),
        fetch('/data/profile.json').then(r => r.json()).catch(() => ({}))
      ]);
      state.jobs = resJobs;
      state.applied = resApplied;
      state.profile = resProfile;
      saveToLocalStorage();
    }
  } catch (err) {
    console.error('Error cargando datos:', err);
  }
}

function saveToLocalStorage() {
  localStorage.setItem('jobagent_applied', JSON.stringify(state.applied));
  localStorage.setItem('jobagent_jobs', JSON.stringify(state.jobs));
  localStorage.setItem('jobagent_profile', JSON.stringify(state.profile));
}

// Navigation Tabs
function initNavigation() {
  const navItems = document.querySelectorAll('.nav-item');
  const panes = document.querySelectorAll('.tab-pane');
  const headerTitle = document.getElementById('header-page-title');
  const headerDesc = document.getElementById('header-page-desc');

  const titlesMap = {
    'tab-available': {
      title: 'Empleos Disponibles para Postular',
      desc: 'Ofertas encontradas en LinkedIn basadas en tu perfil y postulaciones de los últimos 6 meses.'
    },
    'tab-applied': {
      title: 'Mis Postulaciones Realizadas (Referencia para IA)',
      desc: 'Tus empleos postulados sirven de semilla para buscar vacantes similares en LinkedIn.'
    },
    'tab-analytics': {
      title: 'Aprendizaje de IA (Últimos 6 Meses)',
      desc: 'Patrones, tecnologías y titular de LinkedIn usados para emparejar nuevas oportunidades.'
    },
    'tab-profile': {
      title: 'Perfil de LinkedIn y Filtros de Búsqueda',
      desc: 'Configura tus datos de LinkedIn, roles objetivo y palabras clave para las búsquedas.'
    }
  };

  navItems.forEach(item => {
    item.addEventListener('click', () => {
      const tabId = item.getAttribute('data-tab');
      state.activeTab = tabId;

      navItems.forEach(n => n.classList.remove('active'));
      panes.forEach(p => p.classList.remove('active'));

      item.classList.add('active');
      document.getElementById(tabId).classList.add('active');

      if (titlesMap[tabId]) {
        headerTitle.textContent = titlesMap[tabId].title;
        headerDesc.textContent = titlesMap[tabId].desc;
      }
    });
  });
}

// Event Listeners
function initEventListeners() {
  const searchInput = document.getElementById('global-search-input');
  searchInput.addEventListener('input', (e) => {
    state.searchQuery = e.target.value.toLowerCase();
    renderAvailableJobs();
  });

  document.getElementById('filter-min-score').addEventListener('change', (e) => {
    state.minScoreFilter = parseInt(e.target.value) || 0;
    renderAvailableJobs();
  });

  const recentSelect = document.getElementById('filter-recent-only');
  if (recentSelect) {
    recentSelect.addEventListener('change', (e) => {
      state.recentFilter = e.target.value;
      renderAvailableJobs();
    });
  }

  document.getElementById('filter-location').addEventListener('change', (e) => {
    state.locationFilter = e.target.value;
    renderAvailableJobs();
  });

  // Botón de Sincronización con LinkedIn Jobs Tracker
  const btnSync = document.getElementById('btn-sync-linkedin');
  if (btnSync) {
    btnSync.addEventListener('click', handleSyncLinkedIn);
  }

  // Botón de Refrescar Búsqueda en Vivo
  const btnRefresh = document.getElementById('btn-refresh-jobs');
  if (btnRefresh) {
    btnRefresh.addEventListener('click', handleRefreshJobs);
  }

  document.getElementById('btn-export-data').addEventListener('click', exportDataJSON);

  const modal = document.getElementById('modal-add-applied');
  const openModal = () => {
    document.getElementById('modal-date').value = new Date().toISOString().split('T')[0];
    modal.classList.add('active');
  };

  document.getElementById('btn-open-add-applied').addEventListener('click', openModal);
  const btnOpen2 = document.getElementById('btn-open-add-applied-2');
  if (btnOpen2) btnOpen2.addEventListener('click', openModal);

  document.getElementById('btn-close-modal').addEventListener('click', () => {
    modal.classList.remove('active');
  });
  document.getElementById('btn-cancel-modal').addEventListener('click', () => {
    modal.classList.remove('active');
  });

  document.getElementById('add-applied-form').addEventListener('submit', handleAddApplication);
  document.getElementById('profile-form').addEventListener('submit', handleProfileSave);
}

// Sincronizar postulaciones reales desde LinkedIn Jobs Tracker
async function handleSyncLinkedIn() {
  const btn = document.getElementById('btn-sync-linkedin');
  const icon = document.getElementById('sync-icon');

  btn.disabled = true;
  icon.className = 'ri-loader-4-line spin';
  btn.innerHTML = `<i class="ri-loader-4-line spin"></i> Sincronizando con LinkedIn...`;

  try {
    const response = await fetch('/api/sync-applied', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ profile: state.profile })
    });

    if (response.ok) {
      const data = await response.json();
      if (data.applied && data.applied.length > 0) {
        state.applied = data.applied;
        saveToLocalStorage();
        renderAll();
        alert(`✅ Sincronización completada. ${data.applied.length} postulaciones importadas desde LinkedIn Jobs Tracker.`);
      } else {
        alert(`⚠️ ${data.message || 'No se encontraron postulaciones. Verifica que tu cookie li_at esté vigente en el archivo .env'}`);
      }
    } else {
      alert('Error en la sincronización. Asegúrate de correr python3 server.py.');
    }
  } catch (err) {
    console.warn('Error de conexión con servidor:', err);
    alert('No se pudo conectar con el servidor local. Ejecuta: python3 server.py');
  } finally {
    btn.disabled = false;
    btn.innerHTML = `<i class="ri-linkedin-box-fill" id="sync-icon"></i> Sincronizar desde LinkedIn`;
  }
}

// Refrescar vacantes comunicándose con server.py
async function handleRefreshJobs() {
  if (state.isRefreshing) return;
  state.isRefreshing = true;

  const btn = document.getElementById('btn-refresh-jobs');
  const icon = document.getElementById('refresh-icon');
  
  btn.disabled = true;
  icon.className = 'ri-loader-4-line spin';
  btn.innerHTML = `<i class="ri-loader-4-line spin"></i> Buscando en LinkedIn...`;

  try {
    const response = await fetch('/api/refresh', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        applied: state.applied,
        profile: state.profile
      })
    });

    if (response.ok) {
      const data = await response.json();
      if (data.jobs) {
        state.jobs = data.jobs;
        saveToLocalStorage();
        renderAll();
        alert(`¡Búsqueda completada! Se procesaron ${state.jobs.length} empleos en total con tu perfil de LinkedIn.`);
      }
    } else {
      // Fallback si el servidor no está escuchando peticiones POST
      alert('Se intentó refrescar la búsqueda. Si estás ejecutando en servidor local, asegúrate de correr python3 server.py.');
    }
  } catch (err) {
    console.warn('Backend local no detectado o respuesta estática:', err);
    alert('Búsqueda ejecutada en frontend. Para búsquedas en tiempo real en LinkedIn, ejecuta: python3 server.py en la terminal.');
  } finally {
    state.isRefreshing = false;
    btn.disabled = false;
    btn.innerHTML = `<i class="ri-refresh-line" id="refresh-icon"></i> Buscar Más Vacantes con IA`;
  }
}

// RENDERERS
function renderAll() {
  renderAvailableJobs();
  renderAppliedJobs();
  renderAnalytics();
  renderProfile();
  updateBadgesAndStats();
}

function updateBadgesAndStats() {
  document.getElementById('badge-available-count').textContent = state.jobs.length;
  document.getElementById('badge-applied-count').textContent = state.applied.length;

  document.getElementById('stat-total-applied').textContent = state.applied.length;
  const interviewing = state.applied.filter(a => a.status === 'Entrevista').length;
  const offers = state.applied.filter(a => a.status === 'Oferta').length;

  document.getElementById('stat-interviewing').textContent = interviewing;
  document.getElementById('stat-offers').textContent = offers;
}

function renderAvailableJobs() {
  const container = document.getElementById('available-jobs-container');
  container.innerHTML = '';

  let filtered = state.jobs.filter(job => {
    const alreadyApplied = state.applied.some(a => a.url === job.url || a.title === job.title);
    if (alreadyApplied) return false;

    if (job.match_score < state.minScoreFilter) return false;
    if (state.recentFilter === 'recent_match' && !job.is_recent_match) return false;

    if (state.locationFilter === 'remoto' && !job.location.toLowerCase().includes('remot')) return false;
    if (state.locationFilter === 'chile' && !job.location.toLowerCase().includes('chile')) return false;

    if (state.searchQuery) {
      const q = state.searchQuery;
      const text = `${job.title} ${job.company} ${job.location} ${(job.skills || []).join(' ')}`.toLowerCase();
      if (!text.includes(q)) return false;
    }

    return true;
  });

  const countElem = document.getElementById('displayed-jobs-count');
  if (countElem) countElem.textContent = filtered.length;

  if (filtered.length === 0) {
    container.innerHTML = `
      <div style="grid-column: 1/-1; text-align: center; padding: 40px; color: var(--text-muted);">
        <i class="ri-inbox-line" style="font-size: 48px; display: block; margin-bottom: 12px;"></i>
        <p>No se encontraron empleos que coincidan con los filtros seleccionados.</p>
        <button class="btn btn-primary mt-3" onclick="handleRefreshJobs()">
          <i class="ri-refresh-line"></i> Buscar Nuevas Vacantes en LinkedIn
        </button>
      </div>
    `;
    return;
  }

  filtered.forEach(job => {
    const card = document.createElement('div');
    card.className = 'job-card';

    const matchClass = job.match_score >= 80 ? 'match-high' : 'match-med';

    card.innerHTML = `
      <div class="match-badge ${matchClass}">
        <i class="ri-fire-fill"></i> ${job.match_score}% Match
      </div>
      <div class="job-header">
        <h3>${escapeHtml(job.title)}</h3>
        <span class="job-company"><i class="ri-building-line"></i> ${escapeHtml(job.company)}</span>
      </div>
      <div class="job-meta">
        <span><i class="ri-map-pin-line"></i> ${escapeHtml(job.location)}</span>
        <span><i class="ri-time-line"></i> ${escapeHtml(job.posted_date || 'Reciente')}</span>
      </div>
      <p class="job-desc">${escapeHtml(job.description || '')}</p>
      
      <div class="job-skills">
        ${(job.skills || []).map(s => `<span class="skill-tag">${escapeHtml(s)}</span>`).join('')}
      </div>

      ${job.match_reasons && job.match_reasons.length ? `
        <div class="match-reasons-box">
          <i class="ri-sparkles-line"></i> <strong>IA:</strong> ${job.match_reasons.join('. ')}
        </div>
      ` : ''}

      <div class="job-actions">
        <a href="${job.url}" target="_blank" class="btn btn-secondary">
          <i class="ri-external-link-line"></i> Ver en LinkedIn
        </a>
        <button class="btn btn-primary btn-apply-now" data-id="${job.id}">
          <i class="ri-check-line"></i> Postulé a este Empleo
        </button>
      </div>
    `;

    container.appendChild(card);
  });

  container.querySelectorAll('.btn-apply-now').forEach(btn => {
    btn.addEventListener('click', () => {
      const jobId = btn.getAttribute('data-id');
      markAsApplied(jobId);
    });
  });
}

function markAsApplied(jobId) {
  const job = state.jobs.find(j => j.id === jobId);
  if (!job) return;

  const newApplied = {
    id: `app-${Date.now()}`,
    title: job.title,
    company: job.company,
    location: job.location,
    url: job.url,
    applied_date: new Date().toISOString().split('T')[0],
    status: 'Postulado',
    notes: `Postulado desde sugerencia de IA (${job.match_score}% Match)`,
    description: job.description,
    skills: job.skills || []
  };

  state.applied.unshift(newApplied);
  saveToLocalStorage();
  renderAll();

  alert(`¡Postulación registrada para "${job.title}"! Esta postulación servirá como referencia para las próximas búsquedas en LinkedIn.`);
}

function renderAppliedJobs() {
  const container = document.getElementById('applied-jobs-container');
  container.innerHTML = '';

  if (state.applied.length === 0) {
    container.innerHTML = `
      <div style="text-align: center; padding: 40px; color: var(--text-muted);">
        <p>Aún no has registrado postulaciones. ¡Agrega una para que la IA la use como referencia!</p>
      </div>
    `;
    return;
  }

  state.applied.forEach(app => {
    const item = document.createElement('div');
    item.className = 'applied-item';

    const isFromLinkedIn = app.source === 'linkedin_tracker';
    const linkedinBadge = isFromLinkedIn
      ? `<span style="font-size: 11px; background: rgba(56,189,248,0.15); color: var(--accent-cyan); border: 1px solid rgba(56,189,248,0.3); padding: 2px 8px; border-radius: 10px; margin-left: 8px;"><i class="ri-linkedin-box-fill"></i> LinkedIn</span>`
      : '';

    item.innerHTML = `
      <div class="applied-info">
        <h4>${escapeHtml(app.title)} ${linkedinBadge}</h4>
        <p><strong>${escapeHtml(app.company)}</strong> • ${escapeHtml(app.location)} • Postulado el: ${app.applied_date}</p>
        ${app.notes ? `<p style="margin-top: 6px; font-style: italic; color: var(--accent-cyan);"><i class="ri-sticky-note-line"></i> ${escapeHtml(app.notes)}</p>` : ''}
      </div>
      <div style="display: flex; align-items: center; gap: 12px;">
        <select class="status-select" data-id="${app.id}">
          <option value="Postulado" ${app.status === 'Postulado' ? 'selected' : ''}>Postulado</option>
          <option value="Entrevista" ${app.status === 'Entrevista' ? 'selected' : ''}>Entrevista</option>
          <option value="Oferta" ${app.status === 'Oferta' ? 'selected' : ''}>Oferta Recibida</option>
          <option value="Rechazado" ${app.status === 'Rechazado' ? 'selected' : ''}>Rechazado</option>
        </select>
        ${app.url && app.url !== '#' ? `<a href="${app.url}" target="_blank" class="btn btn-secondary" style="padding: 6px 12px;"><i class="ri-link"></i></a>` : ''}
      </div>
    `;
    container.appendChild(item);
  });

  container.querySelectorAll('.status-select').forEach(sel => {
    sel.addEventListener('change', (e) => {
      const appId = sel.getAttribute('data-id');
      const app = state.applied.find(a => a.id === appId);
      if (app) {
        app.status = e.target.value;
        saveToLocalStorage();
        updateBadgesAndStats();
      }
    });
  });
}

function renderAnalytics() {
  const kwContainer = document.getElementById('learned-keywords-cloud');
  kwContainer.innerHTML = '';

  const counts = {};
  state.applied.forEach(app => {
    (app.skills || []).forEach(s => {
      counts[s] = (counts[s] || 0) + 1;
    });
  });

  const sortedSkills = Object.entries(counts).sort((a, b) => b[1] - a[1]);

  if (sortedSkills.length === 0) {
    kwContainer.innerHTML = '<span style="color: var(--text-muted); font-size: 13px;">Registra postulaciones para ver las palabras clave extraídas en los últimos 6 meses.</span>';
  } else {
    sortedSkills.forEach(([skill, count]) => {
      const tag = document.createElement('span');
      tag.className = 'kw-badge';
      tag.innerHTML = `${escapeHtml(skill)} <strong style="color:#fff; margin-left:4px;">(${count})</strong>`;
      kwContainer.appendChild(tag);
    });
  }

  const linkedinBox = document.getElementById('linkedin-profile-box');
  const url = state.profile.linkedin_profile_url || 'No configurada';
  const headline = state.profile.linkedin_headline || 'Sin titular especificado';

  linkedinBox.innerHTML = `
    <p><strong>Usuario:</strong> ${escapeHtml(state.profile.user_name || 'Esteban Pérez')}</p>
    <p><strong>Titular:</strong> ${escapeHtml(headline)}</p>
    <p style="margin-top: 8px;">
      <a href="${escapeHtml(url)}" target="_blank" style="color: var(--accent-cyan); text-decoration: none;">
        <i class="ri-external-link-line"></i> Abrir Perfil en LinkedIn
      </a>
    </p>
  `;
}

function renderProfile() {
  document.getElementById('prof-name').value = state.profile.user_name || '';
  document.getElementById('prof-linkedin-url').value = state.profile.linkedin_profile_url || '';
  document.getElementById('prof-linkedin-headline').value = state.profile.linkedin_headline || '';
  document.getElementById('prof-target-roles').value = (state.profile.target_roles || []).join(', ');
  document.getElementById('prof-skills').value = (state.profile.skills || []).join(', ');
  document.getElementById('prof-search-keywords').value = (state.profile.search_keywords || []).join(', ');
}

function handleProfileSave(e) {
  e.preventDefault();
  state.profile.user_name = document.getElementById('prof-name').value.trim();
  state.profile.linkedin_profile_url = document.getElementById('prof-linkedin-url').value.trim();
  state.profile.linkedin_headline = document.getElementById('prof-linkedin-headline').value.trim();
  state.profile.target_roles = document.getElementById('prof-target-roles').value.split(',').map(s => s.trim()).filter(Boolean);
  state.profile.skills = document.getElementById('prof-skills').value.split(',').map(s => s.trim()).filter(Boolean);
  state.profile.search_keywords = document.getElementById('prof-search-keywords').value.split(',').map(s => s.trim()).filter(Boolean);

  saveToLocalStorage();
  alert('¡Perfil y datos de LinkedIn guardados! Se utilizarán en las búsquedas automatizadas.');
  renderAll();
}

function handleAddApplication(e) {
  e.preventDefault();
  const title = document.getElementById('modal-title').value.trim();
  const company = document.getElementById('modal-company').value.trim();
  const applied_date = document.getElementById('modal-date').value || new Date().toISOString().split('T')[0];
  const url = document.getElementById('modal-url').value.trim();
  const status = document.getElementById('modal-status').value;
  const notes = document.getElementById('modal-notes').value.trim();

  const newApp = {
    id: `app-manual-${Date.now()}`,
    title,
    company,
    url: url || '#',
    applied_date,
    status,
    notes,
    location: 'No especificada',
    skills: title.split(' ')
  };

  state.applied.unshift(newApp);
  saveToLocalStorage();
  renderAll();

  document.getElementById('modal-add-applied').classList.remove('active');
  document.getElementById('add-applied-form').reset();
}

function exportDataJSON() {
  const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(state.applied, null, 2));
  const downloadAnchor = document.createElement('a');
  downloadAnchor.setAttribute("href", dataStr);
  downloadAnchor.setAttribute("download", "applied_jobs.json");
  document.body.appendChild(downloadAnchor);
  downloadAnchor.click();
  downloadAnchor.remove();
}

function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
