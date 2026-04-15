/* ── City data per country ── */
const CITIES = {
  IN: [
    "Mumbai","Delhi","Bangalore","Hyderabad","Chennai","Kolkata","Pune",
    "Ahmedabad","Jaipur","Surat","Lucknow","Kanpur","Nagpur","Indore",
    "Bhopal","Patna","Vadodara","Gurgaon","Noida","Chandigarh","Kochi",
    "Coimbatore","Guwahati","Bhubaneswar","Visakhapatnam","Remote"
  ],
  US: [
    "New York","San Francisco","Los Angeles","Chicago","Seattle","Boston",
    "Austin","Denver","Atlanta","Dallas","Houston","Washington DC",
    "San Jose","San Diego","Miami","Phoenix","Philadelphia","Remote"
  ],
  GB: [
    "London","Manchester","Birmingham","Leeds","Glasgow","Edinburgh",
    "Bristol","Liverpool","Sheffield","Cambridge","Oxford","Remote"
  ],
  CA: ["Toronto","Vancouver","Montreal","Ottawa","Calgary","Edmonton","Remote"],
  AU: ["Sydney","Melbourne","Brisbane","Perth","Adelaide","Canberra","Remote"],
  SG: ["Singapore","Remote"],
  AE: ["Dubai","Abu Dhabi","Sharjah","Remote"],
  DE: ["Berlin","Munich","Hamburg","Frankfurt","Cologne","Stuttgart","Remote"],
  NL: ["Amsterdam","Rotterdam","The Hague","Utrecht","Remote"],
  JP: ["Tokyo","Osaka","Yokohama","Nagoya","Sapporo","Remote"],
};

/* Sources available per country */
const COUNTRY_SOURCES = {
  IN: [
    { id: "linkedin",   label: "🔵 LinkedIn",   checked: true  },
    { id: "indeed",     label: "🔴 Indeed",     checked: true  },
    { id: "glassdoor",  label: "🟢 Glassdoor",  checked: true  },
    { id: "naukri",     label: "🟡 Naukri",     checked: true  },
    { id: "foundit",    label: "🟠 Foundit",    checked: false },
    { id: "google_jobs",label: "🔍 Google Jobs",checked: false },
    { id: "wellfound",  label: "✨ Wellfound",  checked: false },
  ],
  US: [
    { id: "linkedin",   label: "🔵 LinkedIn",   checked: true  },
    { id: "indeed",     label: "🔴 Indeed",     checked: true  },
    { id: "glassdoor",  label: "🟢 Glassdoor",  checked: true  },
    { id: "google_jobs",label: "🔍 Google Jobs",checked: false },
    { id: "wellfound",  label: "✨ Wellfound",  checked: false },
  ],
  GB: [
    { id: "linkedin",   label: "🔵 LinkedIn",   checked: true  },
    { id: "indeed",     label: "🔴 Indeed",     checked: true  },
    { id: "glassdoor",  label: "🟢 Glassdoor",  checked: true  },
    { id: "google_jobs",label: "🔍 Google Jobs",checked: false },
  ],
  DEFAULT: [
    { id: "linkedin",   label: "🔵 LinkedIn",   checked: true  },
    { id: "indeed",     label: "🔴 Indeed",     checked: true  },
    { id: "glassdoor",  label: "🟢 Glassdoor",  checked: true  },
    { id: "google_jobs",label: "🔍 Google Jobs",checked: false },
    { id: "wellfound",  label: "✨ Wellfound",  checked: false },
  ],
};

/* ── Tag input manager ── */
class TagInput {
  constructor(wrapperId, inputId, suggestionsId, countrySelectId) {
    this.wrapper     = document.getElementById(wrapperId);
    this.input       = document.getElementById(inputId);
    this.sugBox      = document.getElementById(suggestionsId);
    this.countryEl   = document.getElementById(countrySelectId);
    this.tags        = [];
    this._inner      = null;
    this._init();
  }

  _init() {
    this.wrapper.addEventListener('click', () => this.input.focus());

    this.input.addEventListener('keydown', e => {
      if ((e.key === 'Enter' || e.key === ',') && this.input.value.trim()) {
        e.preventDefault();
        this.add(this.input.value.trim().replace(/,$/, ''));
      }
      if (e.key === 'Backspace' && !this.input.value && this.tags.length) {
        this.remove(this.tags[this.tags.length - 1]);
      }
    });

    this.input.addEventListener('input', () => this._showSuggestions());
    this.input.addEventListener('focus', () => this._showSuggestions());
    document.addEventListener('click', e => {
      if (!this.wrapper.contains(e.target) && !this.sugBox.contains(e.target)) {
        this._hideSuggestions();
      }
    });

    // Re-render suggestions when country changes
    if (this.countryEl) {
      this.countryEl.addEventListener('change', () => {
        this.tags = [];
        this._renderTags();
        this._showSuggestions();
        renderSourceCheckboxes(this.countryEl.value);
      });
    }
  }

  add(city) {
    if (!city || this.tags.includes(city)) return;
    this.tags.push(city);
    this.input.value = '';
    this._renderTags();
    this._hideSuggestions();
  }

  remove(city) {
    this.tags = this.tags.filter(t => t !== city);
    this._renderTags();
  }

  _renderTags() {
    const container = document.getElementById('location-tags');
    container.innerHTML = this.tags.map(t => `
      <span class="tag-chip">
        ${escHtml(t)}
        <button type="button" onclick="locationTags.remove('${t.replace(/'/g,"\\'")}')">✕</button>
      </span>
    `).join('');
  }

  _showSuggestions() {
    const country = this.countryEl ? this.countryEl.value : 'IN';
    const cities  = CITIES[country] || CITIES.IN;
    const query   = this.input.value.toLowerCase().trim();
    const matches = cities.filter(c =>
      (!query || c.toLowerCase().includes(query)) && !this.tags.includes(c)
    ).slice(0, 12);

    if (!matches.length) { this._hideSuggestions(); return; }

    if (!this._inner) {
      this._inner = document.createElement('div');
      this._inner.className = 'city-suggestions-inner';
      this.sugBox.appendChild(this._inner);
    }
    this._inner.innerHTML = matches.map(c =>
      `<div class="suggestion-item" onclick="locationTags.add('${c.replace(/'/g,"\\'")}')">
        ${escHtml(c)}
      </div>`
    ).join('');
  }

  _hideSuggestions() {
    if (this._inner) { this._inner.innerHTML = ''; }
  }

  getValues() { return [...this.tags]; }
}

function renderSourceCheckboxes(country) {
  const sources = COUNTRY_SOURCES[country] || COUNTRY_SOURCES.DEFAULT;
  const row = document.getElementById('sources-row');
  row.innerHTML = sources.map(s => `
    <label class="checkbox-label">
      <input type="checkbox" name="source" value="${s.id}" ${s.checked ? 'checked' : ''} />
      <span class="source-badge ${s.id}">${s.label}</span>
    </label>
  `).join('');
}

/* Initialised in app.js DOMContentLoaded */
let locationTags;
