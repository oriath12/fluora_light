/**
 * Fluora Plant Card — Custom Lovelace card for Fluora LED plants
 *
 * Installation:
 *   1. Copy this file to <config>/www/fluora-plant-card.js
 *   2. In Lovelace → Edit Dashboard → Manage Resources add:
 *        URL:  /local/fluora-plant-card.js
 *        Type: JavaScript Module
 *   3. Add a card with type: custom:fluora-plant-card
 *
 * Card config:
 *   type:   custom:fluora-plant-card
 *   entity: light.your_fluora_entity   (required)
 *   name:   My Plant                   (optional display name override)
 *   leaves: []                         (future: per-leaf entity ID list)
 */

// ─── Scene definitions ───────────────────────────────────────────────────────

const SCENES = [
  { effect: "Party",   label: "Party",   icon: "🎉", accent: "#e91e8c" },
  { effect: "Chill",   label: "Chill",   icon: "❄️",  accent: "#42a5f5" },
  { effect: "Focus",   label: "Focus",   icon: "🎯", accent: "#66bb6a" },
  { effect: "Bedtime", label: "Bedtime", icon: "🌙", accent: "#ef6c00" },
  { effect: "Awaken",  label: "Awaken",  icon: "☀️",  accent: "#fdd835" },
  { effect: "Auto",    label: "Auto",    icon: "✨", accent: "#ab47bc" },
];

// ─── CSS ─────────────────────────────────────────────────────────────────────

const STYLES = `
  :host { display: block; }

  .card {
    background: var(--ha-card-background, var(--card-background-color, #1c1c1e));
    border-radius: 16px;
    padding: 20px;
    font-family: var(--primary-font-family, sans-serif);
    color: var(--primary-text-color, #e5e5e7);
    user-select: none;
  }

  /* ── Header ── */
  .header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 4px;
  }
  .name {
    font-size: 1.05rem;
    font-weight: 600;
    opacity: 0.9;
    letter-spacing: -0.01em;
  }
  .power-btn {
    width: 38px;
    height: 38px;
    border-radius: 50%;
    border: none;
    cursor: pointer;
    font-size: 1rem;
    display: flex;
    align-items: center;
    justify-content: center;
    transition: background 0.2s, box-shadow 0.2s;
    flex-shrink: 0;
  }
  .power-btn.on  {
    background: #ffd60a;
    box-shadow: 0 0 14px rgba(255, 214, 10, 0.45);
    color: #1c1c1e;
  }
  .power-btn.off {
    background: var(--secondary-background-color, #2c2c2e);
    color: var(--primary-text-color, #e5e5e7);
  }

  /* ── Plant SVG ── */
  .plant-wrap {
    display: flex;
    justify-content: center;
    margin: 12px 0 16px;
  }
  .plant-wrap svg {
    filter: drop-shadow(0 6px 16px rgba(0,0,0,0.35));
    overflow: visible;
  }
  .leaf-path {
    transition: fill 0.5s ease;
    cursor: default;
  }
  .leaf-path.clickable {
    cursor: pointer;
  }
  .leaf-path.clickable:hover {
    filter: brightness(1.25);
  }

  /* ── Brightness ── */
  .row {
    display: flex;
    align-items: center;
    gap: 10px;
    margin-bottom: 18px;
  }
  .row-label {
    font-size: 0.78rem;
    opacity: 0.5;
    min-width: 20px;
    text-align: center;
  }
  input[type=range] {
    -webkit-appearance: none;
    appearance: none;
    flex: 1;
    height: 6px;
    border-radius: 3px;
    outline: none;
    cursor: pointer;
    background: linear-gradient(
      to right,
      var(--track-fill, #ffd60a) 0%,
      var(--track-fill, #ffd60a) var(--pct, 100%),
      rgba(255,255,255,0.12) var(--pct, 100%)
    );
  }
  input[type=range]::-webkit-slider-thumb {
    -webkit-appearance: none;
    width: 18px;
    height: 18px;
    border-radius: 50%;
    background: #fff;
    box-shadow: 0 1px 5px rgba(0,0,0,0.45);
    cursor: pointer;
    transition: transform 0.1s;
  }
  input[type=range]:active::-webkit-slider-thumb { transform: scale(1.2); }
  .row-value {
    font-size: 0.75rem;
    opacity: 0.5;
    min-width: 34px;
    text-align: right;
  }

  /* ── Section label ── */
  .section-label {
    font-size: 0.68rem;
    text-transform: uppercase;
    letter-spacing: 0.09em;
    opacity: 0.45;
    margin-bottom: 10px;
  }

  /* ── Scene chips ── */
  .scenes {
    display: grid;
    grid-template-columns: repeat(3, 1fr);
    gap: 7px;
    margin-bottom: 20px;
  }
  .scene-btn {
    padding: 10px 4px 8px;
    border-radius: 11px;
    border: 1.5px solid transparent;
    cursor: pointer;
    font-size: 0.76rem;
    font-weight: 500;
    background: var(--secondary-background-color, #2c2c2e);
    color: var(--primary-text-color, #e5e5e7);
    transition: background 0.15s, border-color 0.15s, box-shadow 0.15s;
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 5px;
    line-height: 1;
  }
  .scene-btn .icon { font-size: 1.25rem; }
  .scene-btn.active {
    border-color: var(--ac, #fff);
    background: color-mix(in srgb, var(--ac, #fff) 18%, transparent);
    box-shadow: 0 0 10px color-mix(in srgb, var(--ac, #fff) 40%, transparent);
  }

  /* ── Leaf chips (per-leaf control) ── */
  .leaves-section {
    border-top: 1px solid rgba(255,255,255,0.07);
    padding-top: 16px;
  }
  .leaves-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }
  .leaf-chip {
    position: relative;
    width: 46px;
    height: 46px;
    border-radius: 13px;
    border: 1.5px solid rgba(255,255,255,0.13);
    background: var(--secondary-background-color, #2c2c2e);
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 1.3rem;
    cursor: default;
    transition: border-color 0.3s, box-shadow 0.3s;
  }
  .leaf-chip.live {
    border-color: var(--lc, #4caf50);
    box-shadow: 0 0 8px color-mix(in srgb, var(--lc, #4caf50) 50%, transparent);
    cursor: pointer;
  }
  .leaf-chip .num {
    position: absolute;
    bottom: 3px;
    right: 5px;
    font-size: 0.52rem;
    opacity: 0.55;
    font-family: monospace;
  }
  .hint {
    margin-top: 10px;
    font-size: 0.72rem;
    opacity: 0.38;
    font-style: italic;
    line-height: 1.4;
  }
`;

// ─── Plant SVG helper ─────────────────────────────────────────────────────────

const LEAF_D = "M 0,0 C -10,-5 -12,-22 0,-30 C 12,-22 10,-5 0,0 Z";

// Each entry: [translate-x, translate-y, rotate-deg]
const LEAF_XFORMS = [
  [47, 114, -55],   // lower-left
  [113, 98, 55],    // lower-right
  [50, 82, -38],    // mid-left
  [110, 68, 38],    // mid-right
  [80, 54, 5],      // top-centre
];

function plantSvg(leafColor, isOn) {
  const stem   = isOn ? "#558b2f" : "#3a3a3a";
  const potB   = isOn ? "#795548" : "#444";
  const potR   = isOn ? "#8d6e63" : "#555";
  const soil   = isOn ? "#4e342e" : "#333";

  const leaves = LEAF_XFORMS.map(([tx, ty, r], i) =>
    `<path class="leaf-path" data-idx="${i}"
           d="${LEAF_D}"
           transform="translate(${tx},${ty}) rotate(${r})"
           fill="${leafColor}"/>`
  ).join("\n    ");

  return `
  <svg viewBox="0 0 160 210" width="160" height="210" xmlns="http://www.w3.org/2000/svg">
    <!-- Branches -->
    <path d="M80,140 Q62,126 47,116" stroke="${stem}" stroke-width="2"   fill="none" stroke-linecap="round"/>
    <path d="M80,122 Q97,109 112,100" stroke="${stem}" stroke-width="2"  fill="none" stroke-linecap="round"/>
    <path d="M80,106 Q64,93  51,84"  stroke="${stem}" stroke-width="1.8" fill="none" stroke-linecap="round"/>
    <path d="M80,90  Q95,78  109,70" stroke="${stem}" stroke-width="1.8" fill="none" stroke-linecap="round"/>
    <!-- Main stem -->
    <path d="M80,170 C79,152 81,122 80,57"
          stroke="${stem}" stroke-width="3" fill="none" stroke-linecap="round"/>
    <!-- Leaves -->
    ${leaves}
    <!-- Pot rim -->
    <rect x="42" y="164" width="76" height="9" rx="4.5" fill="${potR}"/>
    <!-- Pot body -->
    <path d="M48,173 L40,206 L120,206 L112,173 Z" fill="${potB}"/>
    <!-- Soil -->
    <ellipse cx="80" cy="166" rx="36" ry="6" fill="${soil}"/>
  </svg>`.trim();
}

// ─── Card class ───────────────────────────────────────────────────────────────

class FluoraPlantCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._config   = {};
    this._hass     = null;
    this._sliding  = false;   // suppress re-renders while slider is dragged
  }

  // Called by HA with the YAML config block
  setConfig(config) {
    if (!config.entity) throw new Error("fluora-plant-card: 'entity' is required");
    this._config = config;
    this._render();
  }

  // Called by HA whenever any entity state changes
  set hass(hass) {
    this._hass = hass;
    if (!this._sliding) this._render();
  }

  getCardSize() { return 6; }

  static getStubConfig() {
    return { entity: "light.fluora_light" };
  }

  // ── State helpers ────────────────────────────────────────────────────────

  get _stateObj() {
    return this._hass?.states[this._config.entity] ?? null;
  }
  get _isOn()   { return this._stateObj?.state === "on"; }
  get _briPct() {
    const b = this._stateObj?.attributes?.brightness;
    return b != null ? Math.round(b / 2.55) : 100;
  }
  get _hsColor() { return this._stateObj?.attributes?.hs_color ?? null; }
  get _effect()  { return this._stateObj?.attributes?.effect ?? null; }
  get _name()    {
    return this._config.name
      ?? this._stateObj?.attributes?.friendly_name
      ?? this._config.entity;
  }

  _leafColor() {
    if (!this._isOn()) return "#222";
    const hs  = this._hsColor;
    const bri = this._briPct;
    const L   = Math.round(12 + bri * 0.42);
    if (!hs) return `hsl(0,0%,${L}%)`;
    return `hsl(${Math.round(hs[0])},${Math.round(hs[1])}%,${L}%)`;
  }

  _trackColor() {
    if (!this._isOn()) return "rgba(255,255,255,0.15)";
    const hs = this._hsColor;
    if (!hs) return "#ffd60a";
    return `hsl(${Math.round(hs[0])},${Math.round(hs[1])}%,55%)`;
  }

  // ── Actions ──────────────────────────────────────────────────────────────

  _svc(service, data = {}) {
    this._hass.callService("light", service, {
      entity_id: this._config.entity, ...data,
    });
  }
  _toggle()         { this._svc(this._isOn() ? "turn_off" : "turn_on"); }
  _setEffect(eff)   { this._svc("turn_on", { effect: eff }); }
  _setBri(pct)      { this._svc("turn_on", { brightness: Math.round(pct * 2.55) }); }

  // ── Render ───────────────────────────────────────────────────────────────

  _render() {
    const on      = this._isOn();
    const bri     = this._briPct;
    const effect  = this._effect;
    const lColor  = this._leafColor();
    const tColor  = this._trackColor();
    const leaves  = this._config.leaves ?? [];

    // Scene buttons
    const sceneBtns = SCENES.map(s => {
      const active = effect === s.effect;
      return `<button class="scene-btn${active ? " active" : ""}"
                      data-effect="${s.effect}"
                      ${active ? `style="--ac:${s.accent}"` : ""}>
                <span class="icon">${s.icon}</span>${s.label}
              </button>`;
    }).join("");

    // Leaf chips
    let leafHtml;
    if (leaves.length > 0) {
      leafHtml = leaves.map((eid, i) => {
        const st  = this._hass?.states[eid];
        const hs  = st?.attributes?.hs_color;
        const lc  = hs ? `hsl(${Math.round(hs[0])},${Math.round(hs[1])}%,45%)` : "#2c2c2e";
        return `<div class="leaf-chip live" data-entity="${eid}"
                     style="--lc:${lc};background:color-mix(in srgb,${lc} 20%,transparent)">
                  🍃<span class="num">${i + 1}</span>
                </div>`;
      }).join("");
    } else {
      leafHtml = Array.from({ length: 5 }, (_, i) =>
        `<div class="leaf-chip"><span style="opacity:.4">🍃</span><span class="num">${i + 1}</span></div>`
      ).join("");
    }

    this.shadowRoot.innerHTML = `
      <style>${STYLES}</style>
      <div class="card">

        <div class="header">
          <span class="name">🌿 ${this._name}</span>
          <button class="power-btn ${on ? "on" : "off"}" id="pwrBtn">⏻</button>
        </div>

        <div class="plant-wrap">
          ${plantSvg(lColor, on)}
        </div>

        <div class="row">
          <span class="row-label" style="font-size:0.9rem">☀</span>
          <input type="range" id="briSlider" min="1" max="100" value="${bri}"
                 style="--pct:${bri}%;--track-fill:${tColor}"/>
          <span class="row-value" id="briVal">${bri}%</span>
        </div>

        <div class="section-label">Scene</div>
        <div class="scenes">${sceneBtns}</div>

        <div class="leaves-section">
          <div class="section-label">Individual Leaves</div>
          <div class="leaves-grid">${leafHtml}</div>
          ${leaves.length === 0
            ? `<p class="hint">Per-leaf control will appear here once leaf entities are
               discovered via the Wireshark protocol capture.
               Add a <code>leaves:</code> list to this card's config to enable it.</p>`
            : ""}
        </div>

      </div>`;

    // ── Event listeners ───────────────────────────────────────────────────

    this.shadowRoot.getElementById("pwrBtn")
      ?.addEventListener("click", () => this._toggle());

    this.shadowRoot.querySelectorAll(".scene-btn").forEach(btn =>
      btn.addEventListener("click", e =>
        this._setEffect(e.currentTarget.dataset.effect)
      )
    );

    const slider = this.shadowRoot.getElementById("briSlider");
    const valLbl = this.shadowRoot.getElementById("briVal");
    slider?.addEventListener("input", e => {
      this._sliding = true;
      const pct = +e.target.value;
      e.target.style.setProperty("--pct", pct + "%");
      if (valLbl) valLbl.textContent = pct + "%";
    });
    slider?.addEventListener("change", e => {
      this._sliding = false;
      this._setBri(+e.target.value);
    });

    // Per-leaf chips (live entities only)
    this.shadowRoot.querySelectorAll(".leaf-chip.live").forEach(chip =>
      chip.addEventListener("click", e => {
        const eid = e.currentTarget.dataset.entity;
        // Fire a more-info dialog for the leaf entity
        this.dispatchEvent(new CustomEvent("hass-more-info", {
          bubbles: true, composed: true,
          detail: { entityId: eid },
        }));
      })
    );
  }
}

customElements.define("fluora-plant-card", FluoraPlantCard);

// Register with the Lovelace custom card picker
window.customCards = window.customCards || [];
window.customCards.push({
  type:        "fluora-plant-card",
  name:        "Fluora Plant Card",
  description: "Control your Fluora LED plant — colour wheel, scenes, and per-leaf control",
  preview:     false,
});
