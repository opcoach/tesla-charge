from __future__ import annotations

from datetime import datetime
from typing import Any

from flask import Flask, jsonify, render_template_string, request

from config import AppConfig
from control_loop import ControlLoop
from solar_monitor import SolarMonitor
from tesla_controller import TeslaController


DASHBOARD_HTML = """
<!doctype html>
<html lang="fr">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Tesla Charge</title>
  <style>
    :root {
      --bg: #f5f3ed;
      --card: #fffdf8;
      --line: #d8d0c2;
      --ink: #23201a;
      --muted: #6d665d;
      --accent: #007a5a;
      --warn: #b35c00;
      --danger: #b3261e;
      --accent-2: #2c5aa0;
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      font-family: "Avenir Next", "Segoe UI", sans-serif;
      background:
        radial-gradient(circle at top left, rgba(0,122,90,0.12), transparent 28%),
        linear-gradient(180deg, #faf7f0, var(--bg));
      color: var(--ink);
    }
    main {
      max-width: 980px;
      margin: 0 auto;
      padding: 24px 16px 40px;
    }
    .title-row {
      position: relative;
      display: flex;
      align-items: flex-start;
      gap: 12px;
      margin-bottom: 8px;
    }
    .title-lockup {
      position: relative;
      display: inline-flex;
      align-items: flex-start;
    }
    .refresh-orb {
      position: absolute;
      left: -24px;
      top: 14px;
      width: 18px;
      height: 18px;
      padding: 0;
      border-radius: 999px;
      border: 2px solid rgba(0, 122, 90, 0.14);
      background:
        conic-gradient(var(--accent) 0deg, rgba(0, 122, 90, 0.12) 0deg);
      box-shadow: 0 0 0 1px rgba(255, 253, 248, 0.95) inset;
      cursor: pointer;
      appearance: none;
      -webkit-appearance: none;
      outline: none;
    }
    .refresh-orb:hover {
      border: 2px solid rgba(0, 122, 90, 0.14);
      filter: saturate(1.1);
    }
    .refresh-orb::after {
      content: "";
      position: absolute;
      inset: 4px;
      border-radius: 999px;
      background: var(--card);
    }
    h1 {
      margin: 0;
      font-size: clamp(2rem, 6vw, 3.1rem);
      line-height: 1;
      letter-spacing: -0.04em;
    }
    .subhead {
      color: var(--muted);
      margin-bottom: 18px;
    }
    .timing {
      display: flex;
      flex-wrap: wrap;
      gap: 8px;
      margin-bottom: 24px;
    }
    .timing .pill {
      display: inline-flex;
      align-items: center;
      flex-wrap: wrap;
      gap: 6px;
      background: rgba(255, 253, 248, 0.9);
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 0.76rem;
      padding: 7px 10px;
      min-width: 260px;
      white-space: nowrap;
    }
    .pill-hint {
      color: var(--muted);
      font-size: 0.68rem;
    }
    .pill-strong {
      color: var(--ink);
      font-weight: 700;
    }
    .cadence-select {
      appearance: none;
      -webkit-appearance: none;
      background: rgba(255, 253, 248, 0.95);
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--ink);
      font: inherit;
      font-size: 0.72rem;
      padding: 4px 8px;
      outline: none;
    }
    .cadence-select.is-default {
      font-weight: 700;
    }
    .pill-action {
      border: 1px solid var(--line);
      background: rgba(255, 253, 248, 0.95);
      color: var(--ink);
      border-radius: 999px;
      width: 26px;
      height: 26px;
      padding: 0;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      line-height: 1;
      font-size: 0.8rem;
    }
    .pill-action:hover {
      border-color: var(--accent);
      color: var(--accent);
    }
    .automation-toggle {
      border: 1px solid var(--line);
      background: rgba(255, 253, 248, 0.95);
      color: var(--accent);
      border-radius: 999px;
      min-width: 58px;
      height: 26px;
      padding: 0 12px;
      display: inline-flex;
      align-items: center;
      justify-content: center;
      cursor: pointer;
      font: inherit;
      font-size: 0.74rem;
      font-weight: 700;
      line-height: 1;
    }
    .automation-toggle.is-off {
      color: var(--danger);
    }
    .automation-toggle:hover {
      border-color: var(--accent);
    }
    .timing select:not(.cadence-select) {
      background: transparent;
      border: 0;
      color: var(--ink);
      font: inherit;
      outline: none;
      padding-left: 6px;
    }
    .summary-row {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin-bottom: 24px;
    }
    .sync-row {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(3, minmax(0, 1fr));
      margin-bottom: 24px;
    }
    .card {
      background: var(--card);
      border: 1px solid var(--line);
      border-radius: 18px;
      padding: 14px;
      box-shadow: 0 12px 30px rgba(35, 32, 26, 0.06);
    }
    .card-top {
      display: flex;
      align-items: flex-start;
      justify-content: space-between;
      gap: 10px;
      margin-bottom: 8px;
    }
    .card-title {
      display: flex;
      flex-direction: column;
      gap: 2px;
      min-width: 0;
    }
    .label {
      color: var(--muted);
      font-size: 0.72rem;
      line-height: 1.2;
    }
    .value {
      font-size: clamp(1rem, 2.5vw, 1.32rem);
      font-weight: 600;
      letter-spacing: -0.02em;
      line-height: 1.15;
    }
    .meta-grid {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(auto-fit, minmax(260px, 1fr));
    }
    .meta-line {
      display: flex;
      justify-content: space-between;
      gap: 12px;
      padding: 8px 0;
      border-top: 1px solid var(--line);
      font-size: 0.82rem;
    }
    .meta-line:first-child {
      border-top: 0;
      padding-top: 0;
    }
    .meta-line span:first-child {
      color: var(--muted);
    }
    .chart-controls {
      display: flex;
      justify-content: flex-end;
      margin-bottom: 12px;
    }
    .chart-controls .pill {
      display: inline-flex;
      align-items: center;
      gap: 8px;
    }
    .chart-stack {
      display: grid;
      gap: 14px;
      grid-template-columns: 1fr;
      margin-bottom: 24px;
    }
    .chart-card {
      padding: 14px 14px 12px;
    }
    .chart-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .chart-title {
      font-size: 0.88rem;
      font-weight: 600;
      color: var(--ink);
    }
    .chart-subtitle {
      color: var(--muted);
      font-size: 0.72rem;
    }
    .chart-svg {
      width: 100%;
      height: auto;
      display: block;
      overflow: visible;
    }
    .chart-legend {
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-top: 10px;
      color: var(--muted);
      font-size: 0.78rem;
    }
    .legend-item {
      display: inline-flex;
      align-items: center;
      gap: 6px;
    }
    .legend-swatch {
      width: 12px;
      height: 12px;
      border-radius: 999px;
      display: inline-block;
    }
    .legend-line {
      width: 18px;
      height: 3px;
      border-radius: 999px;
      display: inline-block;
    }
    .chart-head-actions {
      display: flex;
      align-items: center;
      gap: 8px;
    }
    .zoom-button {
      border: 1px solid var(--line);
      background: rgba(255, 253, 248, 0.92);
      color: var(--ink);
      border-radius: 999px;
      padding: 5px 10px;
      font: inherit;
      font-size: 0.75rem;
      cursor: pointer;
    }
    .zoom-button:hover {
      border-color: var(--accent);
      color: var(--accent);
    }
    .chart-help {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 18px;
      margin-left: 6px;
      border-radius: 999px;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.7rem;
      cursor: help;
    }
    .info-icon {
      display: inline-flex;
      align-items: center;
      justify-content: center;
      width: 18px;
      height: 18px;
      flex: 0 0 auto;
      border-radius: 999px;
      border: 1px solid var(--line);
      color: var(--muted);
      font-size: 0.7rem;
      line-height: 1;
      cursor: help;
      background: rgba(255, 253, 248, 0.9);
    }
    .chart-card[data-zoomed="true"] {
      border-color: rgba(0, 122, 90, 0.45);
      box-shadow: 0 16px 36px rgba(35, 32, 26, 0.08);
    }
    .state-ok { color: var(--accent); }
    .state-warn { color: var(--warn); }
    .state-error { color: var(--danger); }
    .footer {
      margin-top: 24px;
      color: var(--muted);
      font-size: 0.92rem;
    }
    @media (max-width: 640px) {
      main {
        padding: 18px 12px 28px;
      }
      .timing {
        gap: 8px;
      }
      .timing .pill {
        width: 100%;
        min-width: 0;
        justify-content: space-between;
      }
      .summary-row {
        grid-template-columns: 1fr;
      }
      .sync-row {
        grid-template-columns: 1fr;
      }
      .chart-row {
        grid-template-columns: 1fr;
      }
      .chart-head {
        flex-direction: column;
        align-items: flex-start;
      }
      .chart-head-actions {
        width: 100%;
        justify-content: flex-start;
        flex-wrap: wrap;
      }
      .chart-title {
        font-size: 0.84rem;
      }
      .chart-subtitle {
        font-size: 0.68rem;
      }
      .chart-svg {
        height: 180px;
      }
      .chart-legend {
        gap: 8px;
        font-size: 0.72rem;
      }
      .card {
        border-radius: 14px;
        padding: 12px;
      }
      .label {
        font-size: 0.69rem;
      }
      .value {
        font-size: clamp(0.96rem, 4vw, 1.18rem);
      }
    }
  </style>
</head>
<body>
  <main>
    <div class="title-row">
      <div class="title-lockup">
        <button class="refresh-orb" id="refresh-orb" type="button" title="Rafraîchir le tableau de bord maintenant" aria-label="Rafraîchir le tableau de bord maintenant"></button>
        <h1>Tesla Charge</h1>
      </div>
    </div>
    <div class="subhead">
      Résumé de la charge sur surplus solaire.
    </div>
    <div class="timing">
      <div class="pill">
        <span>Auto</span>
        <button id="automation-toggle" class="automation-toggle" type="button" aria-pressed="true" title="Basculer entre régulation automatique et reprise manuelle">ON</button>
        <span class="pill-hint" id="automation-hint">régulation automatique</span>
      </div>
      <div class="pill">Mode : <span id="schedule-mode">--</span></div>
      <div class="pill">
        <span>Solaire</span>
        <select id="loop-interval-select" class="cadence-select is-default" data-current="{{ loop_interval_seconds }}" data-default="{{ loop_interval_seconds }}" aria-label="Changer la cadence de régulation"></select>
        <button class="pill-action" type="button" data-refresh-action="loop" title="Forcer une lecture et une régulation maintenant">↻</button>
        <span class="pill-hint"><span id="loop-countdown">--</span></span>
      </div>
      <div class="pill">
        <span>Tesla</span>
        <select id="tesla-interval-select" class="cadence-select is-default" data-current="{{ tesla_refresh_seconds }}" data-default="{{ tesla_refresh_seconds }}" aria-label="Changer la cadence de lecture Tesla"></select>
        <button class="pill-action" type="button" data-refresh-action="tesla" title="Forcer une lecture Tesla maintenant">↻</button>
        <span class="pill-hint" id="tesla-countdown-wrap"><span id="tesla-countdown">--</span></span>
      </div>
    </div>

    <section class="summary-row">
      <article class="card">
        <div class="card-top">
          <div class="card-title">
            <div class="label">Production solaire</div>
          </div>
          <span class="info-icon" title="Puissance instantanée produite par l'installation photovoltaïque.">i</span>
        </div>
        <div class="value" id="production">--</div>
      </article>
      <article class="card">
        <div class="card-top">
          <div class="card-title">
            <div class="label">Consommation maison</div>
          </div>
          <span class="info-icon" title="Puissance instantanée consommée par la maison. La charge Tesla peut en faire partie selon le moment.">i</span>
        </div>
        <div class="value" id="house">--</div>
      </article>
      <article class="card">
        <div class="card-top">
          <div class="card-title">
            <div class="label">Réseau</div>
          </div>
          <span class="info-icon" title="Solde réseau: export négatif, import positif. Le but est de rester le plus souvent proche de l'export nul.">i</span>
        </div>
        <div class="value" id="grid">--</div>
      </article>
    </section>

    <section class="summary-row">
      <article class="card">
        <div class="card-top">
          <div class="card-title">
            <div class="label">Batterie Tesla</div>
          </div>
          <span class="info-icon" title="Pourcentage de charge actuel de la batterie du véhicule.">i</span>
        </div>
        <div class="value" id="battery">--</div>
      </article>
      <article class="card">
        <div class="card-top">
          <div class="card-title">
            <div class="label">État de charge</div>
          </div>
          <span class="info-icon" title="État de charge remonté par l'API Tesla, par exemple Charging ou Stopped.">i</span>
        </div>
        <div class="value" id="charging-state">--</div>
      </article>
      <article class="card">
        <div class="card-top">
          <div class="card-title">
            <div class="label">Intensité Tesla</div>
          </div>
          <span class="info-icon" title="Courant actuellement appliqué à la charge du véhicule.">i</span>
        </div>
        <div class="value" id="amps">--</div>
      </article>
    </section>

    <div class="chart-controls">
      <div class="pill">
        Fenêtre courbe
        <select id="chart-window">
          <option value="900">15 min</option>
          <option value="1800">30 min</option>
          <option value="3600" selected>1 h</option>
        </select>
      </div>
    </div>

    <section class="chart-stack">
      <article class="card chart-card" data-chart="power">
        <div class="chart-head">
          <div>
            <div class="chart-title">
              Puissance produite et consommée
            </div>
            <div class="chart-subtitle">Si Maison est au-dessus de Production, la maison consomme plus qu'elle ne produit.</div>
          </div>
          <div class="chart-head-actions">
            <span class="chart-help" title="Montre la production solaire et la consommation maison. La courbe réseau est séparée pour éviter de confondre export et import avec le reste.">i</span>
            <button class="zoom-button" type="button" data-zoom="power" title="Zoomer sur une fenêtre plus courte">Zoom</button>
          </div>
        </div>
        <svg id="power-chart" class="chart-svg" viewBox="0 0 960 240" role="img" aria-label="Courbe de production et consommation"></svg>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-line" style="background: var(--accent);"></span>Production</span>
          <span class="legend-item"><span class="legend-line" style="background: var(--warn);"></span>Maison</span>
        </div>
      </article>

      <article class="card chart-card" data-chart="grid">
        <div class="chart-head">
          <div>
            <div class="chart-title">
              Import du réseau
            </div>
            <div class="chart-subtitle">Export négatif, import positif, zéro en bleu pour lire l'équilibre.</div>
          </div>
          <div class="chart-head-actions">
            <span class="chart-help" title="Montre l'export et l'import réseau. Les valeurs négatives sont l'export, les valeurs positives l'import.">i</span>
            <button class="zoom-button" type="button" data-zoom="grid" title="Zoomer sur une fenêtre plus courte">Zoom</button>
          </div>
        </div>
        <svg id="grid-chart" class="chart-svg" viewBox="0 0 960 240" role="img" aria-label="Courbe du réseau"></svg>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-line" style="background: var(--danger);"></span>Import > 0</span>
          <span class="legend-item"><span class="legend-line" style="background: var(--accent);"></span>Export < 0</span>
        </div>
      </article>

      <article class="card chart-card" data-chart="amps" id="amps-chart-card">
        <div class="chart-head">
          <div>
            <div class="chart-title">
              Intensité importée dans la Tesla
            </div>
            <div class="chart-subtitle">La consigne est ce qu'on demande, l'intensité est ce que la voiture applique réellement.</div>
          </div>
          <div class="chart-head-actions">
            <span class="chart-help" title="Montre l'intensité réellement appliquée et la consigne calculée pour la voiture.">i</span>
            <button class="zoom-button" type="button" data-zoom="amps" title="Zoomer sur une fenêtre plus courte">Zoom</button>
          </div>
        </div>
        <svg id="amps-chart" class="chart-svg" viewBox="0 0 960 240" role="img" aria-label="Courbe des intensités Tesla"></svg>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-line" style="background: var(--accent-2);"></span>Cible</span>
          <span class="legend-item"><span class="legend-line" style="background: var(--accent);"></span>Intensité</span>
        </div>
      </article>
    </section>

    <section class="meta-grid">
      <article class="card">
        <div class="card-top">
          <div class="card-title">
            <div class="label">Régulation</div>
          </div>
          <span class="info-icon" title="Dernière décision de régulation: surplus, consigne calculée, et dernière mise à jour de la boucle.">i</span>
        </div>
        <div class="meta-line"><span>Surplus exporté</span><strong id="surplus">--</strong></div>
        <div class="meta-line"><span>Cible calculée</span><strong id="target">--</strong></div>
        <div class="meta-line"><span>Dernière décision</span><strong id="decision">--</strong></div>
        <div class="meta-line"><span>Dernière mise à jour</span><strong id="updated-at">--</strong></div>
      </article>
      <article class="card">
        <div class="card-top">
          <div class="card-title">
            <div class="label">Véhicule</div>
          </div>
          <span class="info-icon" title="État du véhicule Tesla détecté par l'API Fleet et dernière commande envoyée.">i</span>
        </div>
        <div class="meta-line"><span>Véhicule</span><strong id="vehicle-name">--</strong></div>
        <div class="meta-line"><span>État véhicule</span><strong id="vehicle-state">--</strong></div>
        <div class="meta-line"><span>Branchée</span><strong id="plugged-in">--</strong></div>
        <div class="meta-line"><span>Dernière consigne</span><strong id="last-commanded-amps">--</strong></div>
        <div class="meta-line"><span>Dernière commande</span><strong id="last-commanded-at">--</strong></div>
        <div class="meta-line"><span>Erreur</span><strong id="error">Aucune</strong></div>
      </article>
    </section>

    <div class="footer">
      API disponibles:
      <code>GET /</code>,
      <code>GET /solar</code>,
      <code>GET /tesla</code>,
      <code>GET /status</code>,
      <code>GET /timeline</code>,
      <code>POST /settings/automation</code>,
      <code>POST /settings/cadences</code>,
      <code>POST /actions/refresh/loop</code>,
      <code>POST /actions/refresh/tesla</code>,
      <code>POST /tesla/amps</code>
    </div>
  </main>

  <script>
    const refreshMs = {{ refresh_ms }};
    const historyWindowSeconds = {{ history_window_seconds }};
    const teslaRefreshSeconds = {{ tesla_refresh_seconds }};
    const zoomWindowSeconds = 600;
    const cadenceOptions = [5, 10, 15, 30, 60, 120, 300];
    const powerChartId = "power-chart";
    const gridChartId = "grid-chart";
    const ampsChartId = "amps-chart";
    const dashboardState = {
      status: null,
      timeline: { window_seconds: historyWindowSeconds, samples: [] },
    };
    const pageState = {
      lastRefreshAt: Date.now(),
    };
    const chartState = {
      power: false,
      grid: false,
      amps: false,
    };
    const chartWindowSelect = document.getElementById("chart-window");
    const loopIntervalSelect = document.getElementById("loop-interval-select");
    const teslaIntervalSelect = document.getElementById("tesla-interval-select");
    const automationToggle = document.getElementById("automation-toggle");
    const automationHint = document.getElementById("automation-hint");
    const teslaCountdownWrap = document.getElementById("tesla-countdown-wrap");
    const ampsChartCard = document.getElementById("amps-chart-card");
    const storedWindow = localStorage.getItem("tesla-charge-chart-window");
    if (storedWindow && ["900", "1800", "3600"].includes(storedWindow)) {
      chartWindowSelect.value = storedWindow;
    }

    function populateCadenceSelect(select) {
      if (!select) return;
      const current = parseInt(select.dataset.current || "", 10);
      const defaultValue = parseInt(select.dataset.default || "", 10);
      select.innerHTML = "";
      cadenceOptions.forEach((value) => {
        const option = document.createElement("option");
        option.value = String(value);
        option.textContent = `${value} s`;
        if (Number.isFinite(current) && current === value) {
          option.selected = true;
        }
        select.appendChild(option);
      });
      select.classList.toggle("is-default", Number.isFinite(current) && current === defaultValue);
    }

    function syncCadenceSelectClass(select) {
      if (!select) return;
      const defaultValue = parseInt(select.dataset.default || "", 10);
      const current = parseInt(select.value, 10);
      select.classList.toggle("is-default", Number.isFinite(current) && current === defaultValue);
    }

    populateCadenceSelect(loopIntervalSelect);
    populateCadenceSelect(teslaIntervalSelect);

    function fmtWatts(value) {
      if (value === null || value === undefined) return "--";
      return `${value} W`;
    }

    function fmtAmps(value) {
      if (value === null || value === undefined) return "--";
      return `${value} A`;
    }

    function fmtPercent(value) {
      if (value === null || value === undefined) return "--";
      return `${value} %`;
    }

    function fmtDate(value) {
      if (!value) return "--";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return new Intl.DateTimeFormat("fr-FR", {
        dateStyle: "short",
        timeStyle: "medium"
      }).format(date);
    }

    function fmtTime(value) {
      if (!value) return "--";
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return value;
      return new Intl.DateTimeFormat("fr-FR", {
        timeStyle: "medium"
      }).format(date);
    }

    function formatScheduleMode(mode) {
      switch (mode) {
        case "active_day":
          return "actif";
        case "idle_night":
          return "veille";
        case "manual_override":
          return "manuel";
        case "manual_refresh":
          return "rafraîchissement";
        default:
          return mode || "--";
      }
    }

    function setText(id, value, className) {
      const node = document.getElementById(id);
      if (!node.dataset.baseClass) {
        node.dataset.baseClass = node.className || "";
      }
      node.textContent = value;
      node.className = [node.dataset.baseClass, className || ""].filter(Boolean).join(" ");
    }

    function isoToMs(value) {
      if (!value) return null;
      const date = new Date(value);
      if (Number.isNaN(date.getTime())) return null;
      return date.getTime();
    }

    function updateRefreshOrb() {
      const orb = document.getElementById("refresh-orb");
      if (!orb) return;
      const elapsedSeconds = (Date.now() - pageState.lastRefreshAt) / 1000;
      const progress = Math.min(1, Math.max(0, elapsedSeconds / (refreshMs / 1000)));
      const angle = Math.max(0, Math.min(360, progress * 360));
      orb.style.background = `conic-gradient(var(--accent) 0deg ${angle}deg, rgba(0, 122, 90, 0.12) ${angle}deg 360deg)`;
      orb.style.boxShadow = `0 0 0 1px rgba(255, 253, 248, 0.95) inset, 0 0 0 ${Math.round(progress * 4)}px rgba(0, 122, 90, ${0.08 * (1 - progress)})`;
    }

    function updateAutomationToggle(status) {
      if (!automationToggle) return;
      const enabled = status?.loop?.automation_enabled !== false;
      automationToggle.textContent = enabled ? "ON" : "OFF";
      automationToggle.setAttribute("aria-pressed", enabled ? "true" : "false");
      automationToggle.classList.toggle("is-off", !enabled);
      if (teslaIntervalSelect) {
        teslaIntervalSelect.disabled = !enabled;
      }
      if (teslaCountdownWrap) {
        teslaCountdownWrap.style.display = enabled ? "" : "none";
      }
      if (ampsChartCard) {
        ampsChartCard.style.display = enabled ? "" : "none";
      }
      automationToggle.title = enabled
        ? "Régulation automatique active. Cliquer pour passer en reprise manuelle."
        : "Reprise manuelle active. Cliquer pour réactiver la régulation automatique.";
      if (automationHint) {
        automationHint.textContent = enabled
          ? "régulation automatique"
          : "reprise manuelle";
        automationHint.className = enabled ? "pill-hint state-ok" : "pill-hint state-warn";
      }
    }

    function currentWindowSeconds() {
      const select = document.getElementById("chart-window");
      const parsed = parseInt(select.value, 10);
      return Number.isFinite(parsed) ? parsed : historyWindowSeconds;
    }

    function chooseSamples(samples, windowSeconds) {
      if (!samples.length) return [];
      const maxTimestamp = samples.reduce((acc, sample) => {
        const ts = isoToMs(sample.recorded_at);
        return ts === null ? acc : Math.max(acc, ts);
      }, 0);
      const cutoff = maxTimestamp - (windowSeconds * 1000);
      return samples.filter((sample) => {
        const ts = isoToMs(sample.recorded_at);
        return ts !== null && ts >= cutoff;
      });
    }

    function effectiveWindowSeconds(chartName) {
      const baseWindow = currentWindowSeconds();
      if (!chartState[chartName]) {
        return baseWindow;
      }
      return Math.min(baseWindow, zoomWindowSeconds);
    }

    function makeSvgEl(tag, attrs = {}) {
      const el = document.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [key, value] of Object.entries(attrs)) {
        el.setAttribute(key, String(value));
      }
      return el;
    }

    function clearSvg(svg) {
      while (svg.firstChild) {
        svg.removeChild(svg.firstChild);
      }
    }

    function renderLineChart(svgId, samples, options) {
      const svg = document.getElementById(svgId);
      clearSvg(svg);

      if (options.tooltip) {
        const title = makeSvgEl("title", {});
        title.textContent = options.tooltip;
        svg.appendChild(title);
      }

      const width = 960;
      const height = 240;
      const pad = { top: 18, right: 18, bottom: 30, left: 46 };
      const plotWidth = width - pad.left - pad.right;
      const plotHeight = height - pad.top - pad.bottom;

      const points = samples
        .map((sample) => ({
          sample,
          t: isoToMs(sample.recorded_at),
        }))
        .filter((point) => point.t !== null);

      if (!points.length) {
        const text = makeSvgEl("text", {
          x: width / 2,
          y: height / 2,
          "text-anchor": "middle",
          fill: "var(--muted)",
          "font-size": 16,
        });
        text.textContent = "Aucune donnée";
        svg.appendChild(text);
        return;
      }

      const minT = points[0].t;
      const maxT = points[points.length - 1].t;
      const timeSpan = Math.max(1, maxT - minT);
      const allValues = [];
      for (const series of options.series) {
        for (const point of points) {
          const value = series.value(point.sample);
          if (value === null || value === undefined || Number.isNaN(value)) continue;
          allValues.push(value);
        }
      }
      if (!allValues.length) allValues.push(0);
      let minY = Math.min(...allValues);
      let maxY = Math.max(...allValues);
      if (options.symmetricAroundZero) {
        const maxAbs = Math.max(Math.abs(minY), Math.abs(maxY));
        minY = -maxAbs;
        maxY = maxAbs;
      } else if (options.zeroBaseline) {
        minY = Math.min(minY, 0);
        maxY = Math.max(maxY, 0);
      }
      if (minY === maxY) {
        minY -= 1;
        maxY += 1;
      }
      const yPadding = (maxY - minY) * 0.08;
      minY -= yPadding;
      maxY += yPadding;
      if (options.yFloor !== undefined) {
        minY = Math.min(minY, options.yFloor);
      }
      if (options.yCeil !== undefined) {
        maxY = Math.max(maxY, options.yCeil);
      }

      const xScale = (t) => pad.left + ((t - minT) / timeSpan) * plotWidth;
      const yScale = (value) => pad.top + (1 - ((value - minY) / (maxY - minY))) * plotHeight;

      const background = makeSvgEl("rect", {
        x: 0,
        y: 0,
        width,
        height,
        rx: 18,
        fill: "transparent",
      });
      svg.appendChild(background);

      for (let i = 0; i <= 4; i += 1) {
        const y = pad.top + (plotHeight / 4) * i;
        const grid = makeSvgEl("line", {
          x1: pad.left,
          y1: y,
          x2: width - pad.right,
          y2: y,
          stroke: "rgba(216, 208, 194, 0.45)",
          "stroke-width": 1,
        });
        svg.appendChild(grid);
      }

      if (options.zeroBaseline && minY <= 0 && maxY >= 0) {
        const zeroY = yScale(0);
        const zeroLine = makeSvgEl("line", {
          x1: pad.left,
          y1: zeroY,
          x2: width - pad.right,
          y2: zeroY,
          stroke: options.zeroLineColor || "rgba(44, 90, 160, 0.68)",
          "stroke-dasharray": "6 4",
          "stroke-width": 1.2,
        });
        svg.appendChild(zeroLine);
      }

      for (let i = 0; i <= 4; i += 1) {
        const y = pad.top + (plotHeight / 4) * i;
        const value = maxY - ((maxY - minY) / 4) * i;
        const label = makeSvgEl("text", {
          x: pad.left - 10,
          y: y + 4,
          "text-anchor": "end",
          fill: "var(--muted)",
          "font-size": 12,
        });
        label.textContent = options.formatLabel(value);
        svg.appendChild(label);
      }

      const bottomLeft = makeSvgEl("text", {
        x: pad.left,
        y: height - 8,
        fill: "var(--muted)",
        "font-size": 12,
      });
      bottomLeft.textContent = options.formatTime(points[0].sample.recorded_at);
      svg.appendChild(bottomLeft);

      const bottomRight = makeSvgEl("text", {
        x: width - pad.right,
        y: height - 8,
        "text-anchor": "end",
        fill: "var(--muted)",
        "font-size": 12,
      });
      bottomRight.textContent = options.formatTime(points[points.length - 1].sample.recorded_at);
      svg.appendChild(bottomRight);

      for (const series of options.series) {
        const drawSegment = (parts) => {
          if (parts.length < 2) return;
          const polyline = makeSvgEl("polyline", {
            fill: "none",
            stroke: series.color,
            "stroke-width": 2.8,
            "stroke-linejoin": "round",
            "stroke-linecap": "round",
          });
          polyline.setAttribute("points", parts.join(" "));
          svg.appendChild(polyline);
        };
        let parts = [];
        for (const point of points) {
          const value = series.value(point.sample);
          if (value === null || value === undefined || Number.isNaN(value)) {
            drawSegment(parts);
            parts = [];
            continue;
          }
          if (series.filter && !series.filter(value)) {
            drawSegment(parts);
            parts = [];
            continue;
          }
          parts.push(`${xScale(point.t).toFixed(1)},${yScale(value).toFixed(1)}`);
        }
        drawSegment(parts);
      }

      const markers = points.filter((point) => point.sample.command || point.sample.decision === "started" || point.sample.decision === "stopped");
      for (const point of markers) {
        const x = xScale(point.t);
        const markerY = pad.top + 8;
        const label = point.sample.command || point.sample.decision || "event";
        const markerColor = point.sample.command === "stop" ? "var(--danger)"
          : point.sample.command === "start" || point.sample.command === "start+set" ? "var(--accent)"
          : "var(--warn)";

        const line = makeSvgEl("line", {
          x1: x,
          y1: pad.top,
          x2: x,
          y2: height - pad.bottom,
          stroke: markerColor,
          "stroke-dasharray": "4 4",
          "stroke-width": 1,
          opacity: 0.5,
        });
        svg.appendChild(line);

        const dot = makeSvgEl("circle", {
          cx: x,
          cy: markerY,
          r: 4.5,
          fill: markerColor,
          stroke: "#fffdf8",
          "stroke-width": 1.5,
        });
        svg.appendChild(dot);

        const markerText = makeSvgEl("text", {
          x: x + 6,
          y: markerY + 4,
          fill: markerColor,
          "font-size": 11,
          "font-weight": 700,
        });
        markerText.textContent = label;
        svg.appendChild(markerText);
      }
    }

    function formatCountdown(targetMs, nowMs) {
      if (targetMs === null || targetMs === undefined) return "--";
      const deltaSeconds = Math.round((targetMs - nowMs) / 1000);
      if (deltaSeconds >= 0) {
        return `dans ${deltaSeconds} s`;
      }
      return `à rafraîchir depuis ${Math.abs(deltaSeconds)} s`;
    }

    async function postJson(url, payload) {
      const response = await fetch(url, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(payload || {}),
      });
      const data = await response.json().catch(() => ({}));
      if (!response.ok) {
        throw new Error(data.error || `Erreur ${response.status}`);
      }
      return data;
    }

    function currentTeslaIntervalSeconds(status) {
      return status?.tesla?.status_refresh_seconds || teslaRefreshSeconds;
    }

    function currentLoopIntervalSeconds(status) {
      return status?.loop?.poll_interval_seconds || refreshMs / 1000;
    }

    async function applyCadenceChange() {
      if (!loopIntervalSelect || !teslaIntervalSelect) return;
      const loopInterval = parseInt(loopIntervalSelect.value, 10);
      const teslaInterval = parseInt(teslaIntervalSelect.value, 10);
      const payload = {
        poll_interval_seconds: Number.isFinite(loopInterval) ? loopInterval : null,
        tesla_status_interval_seconds: Number.isFinite(teslaInterval) ? teslaInterval : null,
      };
      const result = await postJson("/settings/cadences", payload);
      loopIntervalSelect.dataset.current = String(result.poll_interval_seconds);
      teslaIntervalSelect.dataset.current = String(result.tesla_status_interval_seconds);
      syncCadenceSelectClass(loopIntervalSelect);
      syncCadenceSelectClass(teslaIntervalSelect);
      await refresh();
    }

    async function triggerManualRefresh(kind) {
      const endpoint = kind === "tesla"
        ? "/actions/refresh/tesla"
        : "/actions/refresh/loop";
      const result = await postJson(endpoint, {});
      if (kind === "tesla" && result?.tesla) {
        if (!dashboardState.status) {
          dashboardState.status = {};
        }
        dashboardState.status.tesla = result.tesla;
        const snapshot = result.tesla.snapshot || {};
        setText("battery", fmtPercent(snapshot.battery_percent));
        setText("charging-state", snapshot.charging_state || "--", snapshot.charging_state === "Charging" ? "state-ok" : "");
        setText("amps", fmtAmps(snapshot.charging_amps));
        setText("vehicle-name", snapshot.vehicle_name || "--");
        setText("vehicle-state", snapshot.vehicle_state || "--", snapshot.vehicle_state === "online" ? "state-ok" : "state-warn");
        setText("plugged-in", snapshot.plugged_in ? "Oui" : "Non", snapshot.plugged_in ? "state-ok" : "state-warn");
        setText("last-commanded-amps", fmtAmps(result.tesla.last_commanded_amps));
        setText("last-commanded-at", fmtDate(result.tesla.last_commanded_at));
        setText("error", result.tesla.last_error || "Aucune", result.tesla.last_error ? "state-error" : "state-ok");
        updateLiveTimers();
        return;
      }
      await refresh();
    }

    async function setAutomationEnabled(enabled) {
      const result = await postJson("/settings/automation", { enabled });
      if (automationToggle) {
        automationToggle.dataset.enabled = String(result.automation_enabled !== false);
      }
      await refresh();
    }

    function updateLiveTimers() {
      const status = dashboardState.status;
      if (!status) return;

      const solar = status.solar?.snapshot || {};
      const tesla = status.tesla?.snapshot || {};
      const loop = status.loop || {};
      const automationEnabled = loop.automation_enabled !== false;
      const nowMs = Date.now();
      const loopInterval = loop.current_interval_seconds || loop.poll_interval_seconds || refreshMs / 1000;
      const teslaInterval = currentTeslaIntervalSeconds(status);
      const loopReference = loop.last_success_at || loop.last_run_at;
      const loopTarget = loopReference && loopInterval
        ? isoToMs(loopReference) + (loopInterval * 1000)
        : null;
      const teslaTarget = tesla.captured_at ? isoToMs(tesla.captured_at) + (teslaInterval * 1000) : null;

      setText("loop-countdown", formatCountdown(loopTarget, nowMs), loopTarget !== null && loopTarget < nowMs ? "state-warn" : "state-ok");
      if (automationEnabled) {
        setText("tesla-countdown", formatCountdown(teslaTarget, nowMs), teslaTarget !== null && teslaTarget < nowMs ? "state-warn" : "state-ok");
      } else {
        setText("tesla-countdown", "manuel", "state-warn");
      }

      updateRefreshOrb();
    }

    async function refresh() {
      try {
        const [statusResponse, timelineResponse] = await Promise.all([
          fetch("/status", { cache: "no-store" }),
          fetch("/timeline", { cache: "no-store" }),
        ]);
        const data = await statusResponse.json();
        const timeline = await timelineResponse.json();
        dashboardState.status = data;
        dashboardState.timeline = timeline;
        pageState.lastRefreshAt = Date.now();
        updateRefreshOrb();

        const solar = data.solar.snapshot || {};
        const tesla = data.tesla.snapshot || {};
        const loop = data.loop || {};
        const automationEnabled = loop.automation_enabled !== false;
        const teslaIntervalSeconds = currentTeslaIntervalSeconds(data);
        const loopIntervalSeconds = currentLoopIntervalSeconds(data);
        const samples = Array.isArray(timeline.samples) ? timeline.samples : [];
        const powerWindow = effectiveWindowSeconds("power");
        const gridWindow = effectiveWindowSeconds("grid");
        const ampsWindow = effectiveWindowSeconds("amps");

        const gridLabel = solar.grid_watts < 0
          ? `Export ${Math.abs(solar.grid_watts)} W`
          : solar.grid_watts === undefined
            ? "--"
            : `Import ${solar.grid_watts} W`;

        setText("production", fmtWatts(solar.production_watts));
        setText("house", fmtWatts(solar.house_consumption_watts));
        setText("grid", gridLabel, solar.grid_watts < 0 ? "state-ok" : "state-warn");
        setText("battery", fmtPercent(tesla.battery_percent));
        setText("charging-state", tesla.charging_state || "--", tesla.charging_state === "Charging" ? "state-ok" : "");
        setText("amps", fmtAmps(tesla.charging_amps));
        setText("surplus", fmtWatts(solar.export_watts));
        setText("target", fmtAmps(loop.desired_amps));
        setText("decision", loop.last_reason || "--");
        setText("updated-at", fmtDate(loop.last_run_at));
        setText("last-commanded-at", fmtDate(data.tesla.last_commanded_at));
        setText("last-commanded-amps", fmtAmps(data.tesla.last_commanded_amps));
        setText("vehicle-name", tesla.vehicle_name || "--");
        setText("vehicle-state", tesla.vehicle_state || "--", tesla.vehicle_state === "online" ? "state-ok" : "state-warn");
        setText("plugged-in", tesla.plugged_in ? "Oui" : "Non", tesla.plugged_in ? "state-ok" : "state-warn");
        setText("schedule-mode", formatScheduleMode(loop.schedule_mode));
        updateAutomationToggle(data);
        if (loopIntervalSelect) {
          loopIntervalSelect.value = String(loopIntervalSeconds);
          syncCadenceSelectClass(loopIntervalSelect);
        }
        if (teslaIntervalSelect) {
          teslaIntervalSelect.value = String(teslaIntervalSeconds);
          syncCadenceSelectClass(teslaIntervalSelect);
        }
        updateLiveTimers();

        const error = loop.last_error || data.solar.last_error || data.tesla.last_error || "Aucune";
        const errorClass = error === "Aucune" ? "state-ok" : "state-error";
        setText("error", error, errorClass);

        renderLineChart(powerChartId, chooseSamples(samples, powerWindow), {
          series: [
            {
              color: "var(--accent)",
              value: (sample) => sample.production_watts,
            },
            {
              color: "var(--warn)",
              value: (sample) => sample.house_consumption_watts,
            },
          ],
          zeroBaseline: true,
          zeroLineColor: "rgba(44, 90, 160, 0.72)",
          formatLabel: (value) => `${Math.round(value)} W`,
          formatTime: fmtTime,
          tooltip: "Courbe de la production solaire et de la consommation maison. Si Maison passe au-dessus de Production, la maison consomme plus qu'elle ne produit.",
        });

        renderLineChart(gridChartId, chooseSamples(samples, gridWindow), {
          series: [
            {
              color: "var(--danger)",
              value: (sample) => sample.grid_watts,
              filter: (value) => value > 0,
            },
            {
              color: "var(--accent)",
              value: (sample) => sample.grid_watts,
              filter: (value) => value < 0,
            },
          ],
          symmetricAroundZero: true,
          zeroLineColor: "rgba(44, 90, 160, 0.72)",
          formatLabel: (value) => {
            const rounded = Math.round(value);
            return `${rounded > 0 ? "+" : ""}${rounded} W`;
          },
          formatTime: fmtTime,
          tooltip: "Courbe de l'import du réseau: export négatif, import positif. La ligne bleue du zéro correspond à l'équilibre local.",
        });

        if (automationEnabled) {
          renderLineChart(ampsChartId, chooseSamples(samples, ampsWindow), {
            series: [
              {
                color: "var(--accent-2)",
                value: (sample) => sample.desired_amps,
              },
              {
                color: "var(--accent)",
                value: (sample) => sample.charging_amps,
              },
            ],
            zeroBaseline: true,
            yFloor: 0,
            formatLabel: (value) => `${Math.round(value)} A`,
            formatTime: fmtTime,
            tooltip: "Courbe de la consigne calculée et de l'intensité réelle. Si la consigne est au-dessus de l'intensité, la voiture n'a pas encore rattrapé la demande.",
          });
        } else {
          const svg = document.getElementById(ampsChartId);
          if (svg) {
            clearSvg(svg);
          }
        }
      } catch (error) {
        setText("error", error.message || "Erreur inconnue", "state-error");
      }
    }

    refresh();
    setInterval(refresh, refreshMs);
    setInterval(updateLiveTimers, 1000);
    chartWindowSelect.addEventListener("change", () => {
      localStorage.setItem("tesla-charge-chart-window", chartWindowSelect.value);
      if (dashboardState.status && dashboardState.timeline) {
        refresh();
      }
    });
    if (loopIntervalSelect) {
      loopIntervalSelect.addEventListener("change", async () => {
        try {
          await applyCadenceChange();
        } catch (error) {
          setText("error", error.message || "Erreur inconnue", "state-error");
        }
      });
    }
    if (teslaIntervalSelect) {
      teslaIntervalSelect.addEventListener("change", async () => {
        try {
          await applyCadenceChange();
        } catch (error) {
          setText("error", error.message || "Erreur inconnue", "state-error");
        }
      });
    }
    if (automationToggle) {
      automationToggle.addEventListener("click", async () => {
        try {
          automationToggle.disabled = true;
          const enabled = dashboardState.status?.loop?.automation_enabled !== false;
          await setAutomationEnabled(!enabled);
        } catch (error) {
          setText("error", error.message || "Erreur inconnue", "state-error");
        } finally {
          automationToggle.disabled = false;
        }
      });
    }
    const refreshOrb = document.getElementById("refresh-orb");
    if (refreshOrb) {
      refreshOrb.addEventListener("click", async () => {
        try {
          refreshOrb.disabled = true;
          await refresh();
        } catch (error) {
          setText("error", error.message || "Erreur inconnue", "state-error");
        } finally {
          refreshOrb.disabled = false;
        }
      });
    }
    document.querySelectorAll("[data-refresh-action]").forEach((button) => {
      const action = button.getAttribute("data-refresh-action");
      if (!action) return;
      button.addEventListener("click", async () => {
        try {
          button.disabled = true;
          button.classList.add("state-warn");
          await triggerManualRefresh(action);
        } catch (error) {
          setText("error", error.message || "Erreur inconnue", "state-error");
        } finally {
          button.disabled = false;
          button.classList.remove("state-warn");
        }
      });
    });
    document.querySelectorAll("[data-zoom]").forEach((button) => {
      const chartName = button.getAttribute("data-zoom");
      if (!chartName) return;
      const card = document.querySelector(`.chart-card[data-chart="${chartName}"]`);
      const applyZoomLabel = () => {
        button.textContent = chartState[chartName] ? "Dézoomer" : "Zoom";
        if (card) {
          card.dataset.zoomed = chartState[chartName] ? "true" : "false";
        }
      };
      applyZoomLabel();
      button.addEventListener("click", () => {
        chartState[chartName] = !chartState[chartName];
        applyZoomLabel();
        if (dashboardState.status && dashboardState.timeline) {
          refresh();
        }
      });
    });
  </script>
</body>
</html>
"""


def create_app(
    config: AppConfig,
    solar_monitor: SolarMonitor,
    tesla_controller: TeslaController,
    control_loop: ControlLoop,
) -> Flask:
    app = Flask(__name__)

    @app.get("/")
    def dashboard() -> str:
        return render_template_string(
            DASHBOARD_HTML,
            refresh_ms=config.poll_interval_seconds * 1000,
            loop_interval_seconds=config.poll_interval_seconds,
            tesla_refresh_seconds=config.tesla_status_interval_seconds,
            history_window_seconds=config.history_window_seconds,
        )

    @app.get("/solar")
    def solar() -> Any:
        return jsonify(solar_monitor.get_status_payload())

    @app.get("/tesla")
    def tesla() -> Any:
        return jsonify(tesla_controller.get_status_payload())

    @app.get("/status")
    def status() -> Any:
        payload = control_loop.get_status_payload()
        payload["server_time"] = datetime.utcnow().isoformat() + "Z"
        return jsonify(payload)

    @app.get("/timeline")
    def timeline() -> Any:
        payload = control_loop.get_history_payload()
        payload["server_time"] = datetime.utcnow().isoformat() + "Z"
        return jsonify(payload)

    @app.post("/settings/cadences")
    def update_cadences() -> Any:
        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        poll_interval_seconds = payload.get("poll_interval_seconds")
        tesla_status_interval_seconds = payload.get("tesla_status_interval_seconds")
        try:
            result = control_loop.update_runtime_intervals(
                active_poll_interval_seconds=(
                    int(poll_interval_seconds)
                    if poll_interval_seconds not in {None, ""}
                    else None
                ),
                tesla_status_interval_seconds=(
                    int(tesla_status_interval_seconds)
                    if tesla_status_interval_seconds not in {None, ""}
                    else None
                ),
            )
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    @app.post("/settings/automation")
    def update_automation() -> Any:
        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        enabled = payload.get("enabled")
        if isinstance(enabled, str):
            enabled = enabled.strip().lower() in {"1", "true", "yes", "on"}
        elif not isinstance(enabled, bool):
            return jsonify({"error": "Champ enabled obligatoire"}), 400
        try:
            result = control_loop.set_automation_enabled(bool(enabled))
        except Exception as exc:
            return jsonify({"error": str(exc)}), 400
        return jsonify(result)

    @app.post("/actions/refresh/loop")
    def refresh_loop_now() -> Any:
        try:
            payload = control_loop.refresh_now()
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502
        payload["server_time"] = datetime.utcnow().isoformat() + "Z"
        return jsonify(payload)

    @app.post("/actions/refresh/tesla")
    def refresh_tesla_now() -> Any:
        try:
            snapshot = tesla_controller.read_status(force_refresh=True)
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify(
            {
                "server_time": datetime.utcnow().isoformat() + "Z",
                "tesla": tesla_controller.get_status_payload(),
            }
        )

    @app.post("/tesla/amps")
    def set_tesla_amps() -> Any:
        payload = request.get_json(silent=True) or request.form.to_dict() or {}
        amps = payload.get("amps")
        if amps is None:
            return jsonify({"error": "Champ amps obligatoire"}), 400

        try:
            result = tesla_controller.set_charging_amps(int(amps), source="api")
        except Exception as exc:
            return jsonify({"error": str(exc)}), 502
        return jsonify(result)

    return app
