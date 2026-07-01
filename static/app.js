// ══════════════════════════════════════════
//  STATE MANAGEMENT VARIABLES
// ══════════════════════════════════════════
const TRANSLATION_MATRIX_RESOURCES = {
  en: { landingTitle: "Welcome to GovConnect", appHero: "Report. Route. Resolve." },
  te: { landingTitle: "గవర్నమెంట్ కనెక్ట్ కి స్వాగతం", appHero: "నివేదించండి. మార్గదర్శి. పరిష్కరించండి." },
  hi: { landingTitle: "गॉवकनेक्ट में स्वागत है", appHero: "शिकायत करें. मार्गदर्शन करें. समाधान पाएं." }
};

let activeSystemLang = 'en';
let globalLatitudeRef = null;
let globalLongitudeRef = null;
let currentTrackingRefId = null;

// Comprehensive Public Utility & Government Departments for Telangana & Andhra Pradesh
const DEPTS = [
  {id:'maud', icon:'🏙️', name:'MA&UD — Municipal Administration & Urban Development (GHMC/GVMC/VMC)'},
  {id:'trans', icon:'🚌', name:'Transport Department & Road Transport Authority (TSRTA/AP_RTO)'},
  {id:'power', icon:'⚡', name:'Energy Department / Power Distribution (TSSPDCL / TSNPDCL / APEPDCL / APSPDCL)'},
  {id:'water', icon:'💧', name:'Water Supply & Sewerage Board (HMWS&SB / Public Health Engineering)'},
  {id:'home', icon:'🚓', name:'Home Department (State Police, Traffic Enforcement & Law Control)'},
  {id:'r_b', icon:'🛣️', name:'R&B — Roads and Buildings Department'},
  {id:'panchayat', icon:'🏡', name:'Panchayat Raj and Rural Development'},
  {id:'revenue', icon:'📜', name:'Revenue, Land Registration & Land Records Department (CCLA)'},
  {id:'supplies', icon:'🌾', name:'Consumer Affairs, Food & Civil Supplies'},
  {id:'health', icon:'🏥', name:'Health, Medical & Family Welfare Department'}
];

const CAMS = [
  {id:'cam1', name:'MG Road Junction', icon:'🚦', status:'online'},
  {id:'cam2', name:'Railway Station', icon:'🚉', status:'online'}
];

let selectedDepts = new Set();
let db = JSON.parse(localStorage.getItem('gc_db') || '{"citizens":{},"officials":{}}');
let currentUser = null;
let currentRole = null;
let prevPage = 'page-citizen-home';
let compTab = 'text';
let uploadedImg = null;
let analysisRes = null;
let activeCam = 0;
let cctvAlerts = [];

function saveDb() { localStorage.setItem('gc_db', JSON.stringify(db)); }
function showPage(id) {
  document.querySelectorAll('.page').forEach(p => p.classList.remove('active'));
  document.getElementById(id).classList.add('active');
  window.scrollTo(0, 0);
}
function togglePw(id, btn) {
  const el = document.getElementById(id);
  el.type = el.type === 'password' ? 'text' : 'password';
}
function fmtAadhaar(inp) {
  let v = inp.value.replace(/\D/g,'').slice(0,12);
  inp.value = v.replace(/(\d{4})(?=\d)/g,'$1  ');
}

// ══════════════════════════════════════════
//  LOCALIZATION & GEOLOCATION
// ══════════════════════════════════════════
function executeLanguageTransformation(selectedLangCode) {
  activeSystemLang = selectedLangCode;
  const bundle = TRANSLATION_MATRIX_RESOURCES[selectedLangCode] || TRANSLATION_MATRIX_RESOURCES.en;
  document.getElementById('landing-hero-txt').innerHTML = bundle.landingTitle;
  document.getElementById('app-hero-title').innerHTML = bundle.appHero;
}

function extractBrowserSpatialCoordinates() {
  const out = document.getElementById('gis-coordinates-output');
  if (!navigator.geolocation) {
    out.textContent = "Geolocation is not supported by this browser.";
    return;
  }

  out.textContent = "📍 Detecting your location...";

  navigator.geolocation.getCurrentPosition(async pos => {
    globalLatitudeRef = pos.coords.latitude;
    globalLongitudeRef = pos.coords.longitude;

    try {
      const res = await fetch(`/api/reverse-geocode?lat=${globalLatitudeRef}&lon=${globalLongitudeRef}`);
      const data = await res.json();
      
      if (data.success && data.place_name) {
        out.textContent = `GIS Anchored Successfully: ${data.place_name}`;
        const locInput = document.getElementById('loc-inp');
        if (locInput && !locInput.value) {
          locInput.value = data.place_name;
        }
      } else {
        // Fallback directly to raw coordinates if API returned an error structure
        out.textContent = `📍 GIS Anchored: Lat ${globalLatitudeRef.toFixed(5)}, Lon ${globalLongitudeRef.toFixed(5)}`;
      }
    } catch (e) {
      // Fallback directly to raw coordinates if network request fails entirely
      out.textContent = `📍 GIS Anchored: Lat ${globalLatitudeRef.toFixed(5)}, Lon ${globalLongitudeRef.toFixed(5)}`;
    }
  }, err => {
    out.textContent = "Location access denied. Please check your browser permissions.";
  });
}

// ══════════════════════════════════════════
//  GRIEVANCE PORTAL STATUS ENGINE SEARCH
// ══════════════════════════════════════════
async function searchComplaintReferenceId() {
  const token = document.getElementById('search-token-ref-id').value.trim();
  if(!token) return alert("Provide a valid registration token lookup array sequence.");
  
  try {
    const res = await fetch(`/api/complaints/status/${token}`);
    const data = await res.json();
    if(data.error) alert(data.error);
    else {
      alert(`Grievance Tracker Match:\nTitle: ${data.complaint.title}\nStatus Node: ${data.complaint.status}\nDepartment: ${data.complaint.department}`);
    }
  } catch (e) {
    alert("Lookup execution loop connection failure mapping context reference.");
  }
}

// ══════════════════════════════════════════
//  CITIZEN GATEWAY ROUTING PIPELINES
// ══════════════════════════════════════════
async function citizenSignup() {
  const mobile = document.getElementById('cs-mobile').value.trim();
  const name = document.getElementById('cs-fname').value.trim() + " " + document.getElementById('cs-lname').value.trim();
  const email = document.getElementById('cs-email').value.trim();
  const password = document.getElementById('cs-pw').value;
  const state = document.getElementById('cs-state').value;
  const dob = document.getElementById('cs-dob').value;
  const aadhaar = document.getElementById('cs-aadhaar').value.replace(/\s/g,'');

  const payload = { mobile, name, email, password, state, dob, aadhaar };
  
  try {
    const res = await fetch('/api/auth/citizen-signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();
    if(data.error) return alert(data.error);
    
    // Trigger multi-factor Aadhaar validation challenge loop sequence
    const triggerRes = await fetch('/api/auth/aadhaar-trigger-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mobile })
    });
    if((await triggerRes.json()).success) {
      document.getElementById('aadhaar-otp-modal-view').classList.add('open');
    }
  } catch (e) {
    alert("Connection error tracking configuration sequence profiles.");
  }
}

async function validateIdentityVerificationToken() {
  const token = document.getElementById('mfa-token-challenge-input').value.trim();
  const mobile = document.getElementById('cs-mobile').value.trim();
  
  try {
    const res = await fetch('/api/auth/aadhaar-verify-otp', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ mobile, otp: token })
    });
    const data = await res.json();
    if(data.error) alert(data.error);
    else {
      document.getElementById('aadhaar-otp-modal-view').classList.remove('open');
      alert("Multi-Factor Identity validation successful. Secure profile verified.");
      loginAsCitizen(data.user);
    }
  } catch (e) {
    alert("Security framework validation challenge link configuration failure.");
  }
}

function citizenLogin() {
  const id = document.getElementById('cl-id').value.trim();
  const pw = document.getElementById('cl-pw').value;
  
  fetch('/api/auth/citizen-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: id, password: pw })
  }).then(r => r.json()).then(data => {
    if(data.error) alert(data.error);
    else loginAsCitizen(data.user);
  });
}

function loginAsCitizen(user) {
  currentUser = user; currentRole = 'citizen';
  document.getElementById('hdr-name').textContent = user.name.split(' ')[0];
  document.getElementById('user-chip').style.display = 'flex';
  document.getElementById('name-inp').value = user.name;
  document.getElementById('btn-cctv').style.display = 'none';
  showPage('page-citizen-home');
}
function startComplaintRegistration(langCode) {
  document.getElementById('sys-lang-selector').value = langCode;  
  executeLanguageTransformation(langCode);
  showPage('page-citizen-app');
}
// ══════════════════════════════════════════
//  OFFICIAL CHANNELS & CORE ANALYTICS
// ══════════════════════════════════════════
function officialLogin() {
  const id = document.getElementById('ol-id').value.trim();
  const pw = document.getElementById('ol-pw').value;
  
  fetch('/api/auth/official-login', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username: id, password: pw })
  }).then(r => r.json()).then(data => {
    if(data.error) alert(data.error);
    else {
      currentUser = data.user; currentRole = 'official';
      document.getElementById('dash-name').textContent = "Welcome, " + data.user.name;
      document.getElementById('dash-dept').textContent = data.user.district + " Jurisdiction Portal Engine";
      document.getElementById('btn-cctv').style.display = 'inline-block';
      hydrateDepartmentalAnalyticsMetrics();
      showPage('page-official-dash');
    }
  });
}

function hydrateDepartmentalAnalyticsMetrics() {
  fetch('/api/analytics/metrics')
    .then(r => r.json())
    .then(res => {
      if(res.success) {
        const container = document.getElementById('analytics-overview-row');
        container.innerHTML = res.metrics.map(m => `
          <div class="stat-card">
            <div class="stat-num blue">${m.total}</div>
            <div class="stat-label">${m.department} (Total)</div>
          </div>
          <div class="stat-card">
            <div class="stat-num orange">${m.pending}</div>
            <div class="stat-label">Pending Metrics</div>
          </div>
          <div class="stat-card">
            <div class="stat-num green">${m.resolved}</div>
            <div class="stat-label">Resolved Nodes</div>
          </div>
        `).join('');
      }
    });
}

// ══════════════════════════════════════════
//  GRIEVANCE ENGINE SUBSYSTEM PROCEDURES
// ══════════════════════════════════════════
function switchTab(tab) {
  compTab = tab;
  document.getElementById('prob-text').style.display = tab === 'image' ? 'none' : 'block';
  document.getElementById('upload-zone').style.display = tab === 'text' ? 'none' : 'block';
}
function handleFile(e) {
  const file = e.target.files[0]; if(!file) return;
  const r = new FileReader();
  r.onload = ev => { uploadedImg = ev.target.result; document.getElementById('preview-img').src = ev.target.result; document.getElementById('preview-img').style.display='block'; };
  r.readAsDataURL(file);
}

async function analyzeIssue() {
  const text = document.getElementById('prob-text').value.trim();
  document.getElementById('input-section').style.display = 'none';
  document.getElementById('comp-loader').style.display = 'block';

  const payload = {
    text: text,
    location: document.getElementById('loc-inp').value.trim(),
    image: uploadedImg,
    lang: activeSystemLang
  };

  try {
    const res = await fetch('/api/analyze-issue', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    analysisRes = await res.json();
    document.getElementById('comp-loader').style.display = 'none';
    document.getElementById('result-section').style.display = 'block';
    
    document.getElementById('r-dept-name').textContent = analysisRes.department;
    document.getElementById('r-dept-official').textContent = `${analysisRes.official_title}: ${analysisRes.official_name}`;
    document.getElementById('r-dept-contact').textContent = `📧 ${analysisRes.email} | 📞 ${analysisRes.phone}`;
    document.getElementById('r-complaint-box').textContent = analysisRes.complaint_letter;
  } catch(e) {
    alert("AI tracking evaluation pipeline disruption.");
  }
}

async function sendComplaint() {
  const payload = {
    mobile: currentUser ? currentUser.mobile : "ANONYMOUS",
    title: analysisRes.category,
    description: document.getElementById('r-complaint-box').textContent,
    location: document.getElementById('loc-inp').value.trim(),
    latitude: globalLatitudeRef,
    longitude: globalLongitudeRef,
    department: analysisRes.department_short,
    official_title: analysisRes.official_title,
    official_name: analysisRes.official_name,
    priority: analysisRes.priority,
    lang: activeSystemLang,
    image: uploadedImg
  };

  const res = await fetch('/api/complaints/submit', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });
  const data = await res.json();
  if(data.success) {
    currentTrackingRefId = data.ref_id;
    document.getElementById('success-banner').style.display = 'flex';
    document.getElementById('success-msg').textContent = `Forwarded to database registries via reference link code token: ${data.ref_id}`;
    
    document.getElementById('pdf-download-hook').onclick = () => {
       window.location.href = `/api/complaints/export-pdf/${currentTrackingRefId}`;
    };
  }
}

function doLogout() { location.reload();}
function openCCTV() { showPage('page-cctv'); }
function goBackFromCCTV() { showPage(prevPage); }
function resetForm() { location.reload(); }

// ══════════════════════════════════════════
//  PROFILE DETAILS MODAL
// ══════════════════════════════════════════
function openProfileModal() {
  const body = document.getElementById('profile-modal-body');
  if (!currentUser) {
    body.textContent = "You're not signed in yet. Please log in to view your profile.";
  } else if (currentRole === 'citizen') {
    body.textContent =
`Name: ${currentUser.name || '—'}
Mobile: ${currentUser.mobile || '—'}
Email: ${currentUser.email || '—'}
Role: Citizen`;
  } else if (currentRole === 'official') {
    const depts = Array.isArray(currentUser.depts) ? currentUser.depts.join(', ') : (currentUser.depts || '—');
    body.textContent =
`Name: ${currentUser.name || '—'}
Designation: ${currentUser.desig || '—'}
Email: ${currentUser.email || '—'}
District: ${currentUser.district || '—'}
Department(s): ${depts}
Role: Government Official`;
  } else {
    body.textContent = "Profile details are unavailable.";
  }
  document.getElementById('profile-modal-bg').classList.add('open');
}

function closeProfileModal(event) {
  if (event.target.id === 'profile-modal-bg') {
    document.getElementById('profile-modal-bg').classList.remove('open');
  }
}
// Hydrate the interactive Department list checkboxes on load
document.addEventListener("DOMContentLoaded", () => {
  const scrollWrap = document.getElementById("dept-scroll");
  if (!scrollWrap) return;

  // Clear loading placeholder and build checkboxes dynamically
  scrollWrap.innerHTML = DEPTS.map(d => `
    <div class="dept-option" id="opt-${d.id}" onclick="toggleDeptSelection('${d.id}')">
      <input type="checkbox" id="chk-${d.id}" value="${d.id}" onclick="event.stopPropagation(); toggleDeptSelection('${d.id}')">
      <span>${d.icon} ${d.name}</span>
    </div>
  `).join('');
});

// Manage the selected departments list
function toggleDeptSelection(id) {
  const checkbox = document.getElementById(`chk-${id}`);
  const optionEl = document.getElementById(`opt-${id}`);
  
  if (!checkbox || !optionEl) return;

  // Sync state toggling
  if (event.type === 'click' && event.target.tagName !== 'INPUT') {
    checkbox.checked = !checkbox.checked;
  }

  if (checkbox.checked) {
    selectedDepts.add(id);
    optionEl.classList.add('selected');
  } else {
    selectedDepts.delete(id);
    optionEl.classList.remove('selected');
  }

  // Render text badges preview below the list
  const preview = document.getElementById("sel-depts-preview");
  if (preview) {
    preview.innerHTML = Array.from(selectedDepts).map(dId => {
      const match = DEPTS.find(x => x.id === dId);
      return `<span class="badge-selected">${match ? match.icon + ' ' + match.id.toUpperCase() : dId}</span>`;
    }).join('');
  }
}
async function officialSignup() {
  const email = document.getElementById('os-email').value.trim();
  const empid = document.getElementById('os-empid').value.trim();
  const name = document.getElementById('os-name').value.trim();
  const desig = document.getElementById('os-desig').value.trim();
  const phone = document.getElementById('os-phone').value.trim();
  const password = document.getElementById('os-pw').value;
  const passwordConfirm = document.getElementById('os-pw2').value;
  const state = document.getElementById('os-state').value;
  const district = document.getElementById('os-district').value.trim();

  // Validate the required inputs cleanly
  if (!email || !empid || !name || !desig || !phone || !password || !state || !district) {
    document.getElementById('os-err').style.display = 'block';
    document.getElementById('os-err').textContent = "Please fill all required variables matrix fields.";
    return;
  }

  if (password !== passwordConfirm) {
    document.getElementById('os-err').style.display = 'block';
    document.getElementById('os-err').textContent = "Passwords do not match.";
    return;
  }

  if (selectedDepts.size === 0) {
    document.getElementById('os-err').style.display = 'block';
    document.getElementById('os-err').textContent = "Please pick at least one primary department tracking vector.";
    return;
  }

  const payload = {
    email,
    empid,
    name,
    desig,
    phone,
    password,
    state,
    district,
    depts: Array.from(selectedDepts) // Encodes selection array cleanly
  };

  try {
    const res = await fetch('/api/auth/official-signup', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    
    const data = await res.json();
    
    if (data.error) {
      document.getElementById('os-err').style.display = 'block';
      document.getElementById('os-err').textContent = data.error;
    } else {
      document.getElementById('os-err').style.display = 'none';
      alert("Official Registration Successful! Please sign in.");
      showPage('page-o-login');
    }
  } catch (e) {
    alert("Connection error executing official registration loop registry.");
  }
}
