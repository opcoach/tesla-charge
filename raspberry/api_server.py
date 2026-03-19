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
    h1 {
      margin: 0 0 8px;
      font-size: clamp(2rem, 6vw, 3.2rem);
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
      gap: 10px;
      margin-bottom: 24px;
    }
    .timing .pill {
      background: rgba(255, 253, 248, 0.9);
      border: 1px solid var(--line);
      border-radius: 999px;
      color: var(--muted);
      font-size: 0.9rem;
      padding: 8px 12px;
    }
    .timing select {
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
      padding: 18px;
      box-shadow: 0 12px 30px rgba(35, 32, 26, 0.06);
    }
    .label {
      color: var(--muted);
      font-size: 0.92rem;
      margin-bottom: 8px;
    }
    .value {
      font-size: clamp(1.6rem, 4vw, 2.2rem);
      font-weight: 700;
      letter-spacing: -0.04em;
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
      padding: 10px 0;
      border-top: 1px solid var(--line);
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
    .chart-row {
      display: grid;
      gap: 14px;
      grid-template-columns: repeat(2, minmax(0, 1fr));
      margin-bottom: 24px;
    }
    .chart-card {
      padding: 18px 18px 16px;
    }
    .chart-head {
      display: flex;
      align-items: baseline;
      justify-content: space-between;
      gap: 12px;
      margin-bottom: 10px;
    }
    .chart-title {
      font-size: 1rem;
      font-weight: 700;
      color: var(--ink);
    }
    .chart-subtitle {
      color: var(--muted);
      font-size: 0.88rem;
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
      font-size: 0.88rem;
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
      .summary-row {
        grid-template-columns: 1fr;
      }
      .sync-row {
        grid-template-columns: 1fr;
      }
      .chart-row {
        grid-template-columns: 1fr;
      }
      .card {
        border-radius: 14px;
      }
    }
  </style>
</head>
<body>
  <main>
    <h1>Tesla Charge</h1>
    <div class="subhead">
      Résumé de la charge sur surplus solaire.
    </div>
    <div class="timing">
      <div class="pill">Page web : toutes les {{ refresh_ms // 1000 }} s</div>
      <div class="pill">Régulation : <span id="loop-countdown">--</span></div>
      <div class="pill">Tesla : <span id="tesla-countdown">--</span></div>
      <div class="pill">Mode : <span id="schedule-mode">--</span></div>
    </div>

    <section class="sync-row">
      <article class="card">
        <div class="label">Âge de la mesure solaire</div>
        <div class="value" id="solar-age">--</div>
      </article>
      <article class="card">
        <div class="label">Âge de la mesure Tesla</div>
        <div class="value" id="tesla-age">--</div>
      </article>
      <article class="card">
        <div class="label">Écart de mesure</div>
        <div class="value" id="alignment-gap">--</div>
      </article>
    </section>

    <section class="summary-row">
      <article class="card">
        <div class="label">Production solaire</div>
        <div class="value" id="production">--</div>
      </article>
      <article class="card">
        <div class="label">Consommation maison</div>
        <div class="value" id="house">--</div>
      </article>
      <article class="card">
        <div class="label">Réseau</div>
        <div class="value" id="grid">--</div>
      </article>
    </section>

    <section class="summary-row">
      <article class="card">
        <div class="label">Batterie Tesla</div>
        <div class="value" id="battery">--</div>
      </article>
      <article class="card">
        <div class="label">État de charge</div>
        <div class="value" id="charging-state">--</div>
      </article>
      <article class="card">
        <div class="label">Intensité Tesla</div>
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

    <section class="chart-row">
      <article class="card chart-card">
        <div class="chart-head">
          <div class="chart-title">Puissance</div>
          <div class="chart-subtitle">Production, consommation et réseau</div>
        </div>
        <svg id="power-chart" class="chart-svg" viewBox="0 0 960 280" role="img" aria-label="Courbe des puissances"></svg>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-line" style="background: var(--accent);"></span>Production</span>
          <span class="legend-item"><span class="legend-line" style="background: var(--warn);"></span>Maison</span>
          <span class="legend-item"><span class="legend-line" style="background: var(--danger);"></span>Réseau</span>
        </div>
      </article>
      <article class="card chart-card">
        <div class="chart-head">
          <div class="chart-title">Tesla</div>
          <div class="chart-subtitle">Intensité réelle et cible</div>
        </div>
        <svg id="amps-chart" class="chart-svg" viewBox="0 0 960 280" role="img" aria-label="Courbe des intensités Tesla"></svg>
        <div class="chart-legend">
          <span class="legend-item"><span class="legend-line" style="background: var(--accent-2);"></span>Cible</span>
          <span class="legend-item"><span class="legend-line" style="background: var(--accent);"></span>Intensité</span>
          <span class="legend-item"><span class="legend-line" style="background: var(--warn);"></span>Commandes</span>
        </div>
      </article>
    </section>

    <section class="meta-grid">
      <article class="card">
        <div class="meta-line"><span>Surplus exporté</span><strong id="surplus">--</strong></div>
        <div class="meta-line"><span>Cible calculée</span><strong id="target">--</strong></div>
        <div class="meta-line"><span>Dernière décision</span><strong id="decision">--</strong></div>
        <div class="meta-line"><span>Dernière mise à jour</span><strong id="updated-at">--</strong></div>
      </article>
      <article class="card">
        <div class="meta-line"><span>Véhicule</span><strong id="vehicle-name">--</strong></div>
        <div class="meta-line"><span>État véhicule</span><strong id="vehicle-state">--</strong></div>
        <div class="meta-line"><span>Branchée</span><strong id="plugged-in">--</strong></div>
        <div class="meta-line"><span>Dernière commande</span><strong id="last-commanded-at">--</strong></div>
        <div class="meta-line"><span>Erreur</span><strong id="error">Aucune</strong></div>
      </article>
    </section>

    <div class="footer">
      API disponibles: <code>/solar</code>, <code>/tesla</code>, <code>/status</code>, <code>POST /tesla/amps</code>
    </div>
  </main>

  <script>
    const refreshMs = {{ refresh_ms }};
    const historyWindowSeconds = {{ history_window_seconds }};
    const teslaRefreshSeconds = {{ tesla_refresh_seconds }};
    const powerChartId = "power-chart";
    const ampsChartId = "amps-chart";
    const dashboardState = {
      status: null,
      timeline: { window_seconds: historyWindowSeconds, samples: [] },
    };
    const chartWindowSelect = document.getElementById("chart-window");
    const storedWindow = localStorage.getItem("tesla-charge-chart-window");
    if (storedWindow && ["900", "1800", "3600"].includes(storedWindow)) {
      chartWindowSelect.value = storedWindow;
    }

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

    function fmtDuration(seconds) {
      if (seconds === null || seconds === undefined || Number.isNaN(seconds)) return "--";
      const value = Math.max(0, Math.round(seconds));
      if (value < 60) return `${value} s`;
      const minutes = Math.floor(value / 60);
      const remainder = value % 60;
      if (minutes < 60) return `${minutes} min ${String(remainder).padStart(2, "0")} s`;
      const hours = Math.floor(minutes / 60);
      const mins = minutes % 60;
      return `${hours} h ${String(mins).padStart(2, "0")} min`;
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

    function relativeSeconds(baseMs, value) {
      const ts = isoToMs(value);
      if (baseMs === null || ts === null) return null;
      return Math.max(0, (baseMs - ts) / 1000);
    }

    function currentWindowSeconds() {
      const select = document.getElementById("chart-window");
      const parsed = parseInt(select.value, 10);
      return Number.isFinite(parsed) ? parsed : historyWindowSeconds;
    }

    function chooseSamples(samples) {
      const windowSeconds = currentWindowSeconds();
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

      const width = 960;
      const height = 280;
      const pad = { top: 22, right: 22, bottom: 36, left: 52 };
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
      if (options.zeroBaseline) {
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

      if (options.zeroBaseline && minY < 0 && maxY > 0) {
        const zeroY = yScale(0);
        const zeroLine = makeSvgEl("line", {
          x1: pad.left,
          y1: zeroY,
          x2: width - pad.right,
          y2: zeroY,
          stroke: "rgba(179, 92, 0, 0.55)",
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
        y: height - 10,
        fill: "var(--muted)",
        "font-size": 12,
      });
      bottomLeft.textContent = options.formatTime(points[0].sample.recorded_at);
      svg.appendChild(bottomLeft);

      const bottomRight = makeSvgEl("text", {
        x: width - pad.right,
        y: height - 10,
        "text-anchor": "end",
        fill: "var(--muted)",
        "font-size": 12,
      });
      bottomRight.textContent = options.formatTime(points[points.length - 1].sample.recorded_at);
      svg.appendChild(bottomRight);

      for (const series of options.series) {
        const polyline = makeSvgEl("polyline", {
          fill: "none",
          stroke: series.color,
          "stroke-width": 2.8,
          "stroke-linejoin": "round",
          "stroke-linecap": "round",
        });
        const parts = [];
        for (const point of points) {
          const value = series.value(point.sample);
          if (value === null || value === undefined || Number.isNaN(value)) continue;
          parts.push(`${xScale(point.t).toFixed(1)},${yScale(value).toFixed(1)}`);
        }
        polyline.setAttribute("points", parts.join(" "));
        svg.appendChild(polyline);
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

    function updateLiveTimers() {
      const status = dashboardState.status;
      if (!status) return;

      const solar = status.solar?.snapshot || {};
      const tesla = status.tesla?.snapshot || {};
      const loop = status.loop || {};
      const serverTime = isoToMs(status.server_time) || Date.now();

      const loopRemaining = relativeSeconds(serverTime, loop.last_run_at);
      const teslaAge = relativeSeconds(serverTime, tesla.captured_at);
      const solarAge = relativeSeconds(serverTime, solar.captured_at);
      const alignmentGap = solar.captured_at && tesla.captured_at
        ? Math.abs((isoToMs(solar.captured_at) || 0) - (isoToMs(tesla.captured_at) || 0)) / 1000
        : null;

      setText("loop-countdown", `${fmtDuration(loopRemaining)} / ${loop.current_interval_seconds || "--"} s`);
      setText("tesla-countdown", `${fmtDuration(teslaAge)} / ${teslaRefreshSeconds} s`);
      setText("solar-age", fmtDuration(solarAge), solarAge !== null && solarAge > 45 ? "state-warn" : "state-ok");
      setText("tesla-age", fmtDuration(teslaAge), teslaAge !== null && teslaAge > 75 ? "state-warn" : "state-ok");
      setText("alignment-gap", fmtDuration(alignmentGap), alignmentGap !== null && alignmentGap > 20 ? "state-warn" : "state-ok");
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

        const solar = data.solar.snapshot || {};
        const tesla = data.tesla.snapshot || {};
        const loop = data.loop || {};
        const samples = Array.isArray(timeline.samples) ? chooseSamples(timeline.samples) : [];

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
        setText("vehicle-name", tesla.vehicle_name || "--");
        setText("vehicle-state", tesla.vehicle_state || "--", tesla.vehicle_state === "online" ? "state-ok" : "state-warn");
        setText("plugged-in", tesla.plugged_in ? "Oui" : "Non", tesla.plugged_in ? "state-ok" : "state-warn");
        setText("schedule-mode", loop.schedule_mode || "--");
        updateLiveTimers();

        const error = loop.last_error || data.solar.last_error || data.tesla.last_error || "Aucune";
        const errorClass = error === "Aucune" ? "state-ok" : "state-error";
        setText("error", error, errorClass);

        renderLineChart(powerChartId, samples, {
          series: [
            {
              color: "var(--accent)",
              value: (sample) => sample.production_watts,
            },
            {
              color: "var(--warn)",
              value: (sample) => sample.house_consumption_watts,
            },
            {
              color: "var(--danger)",
              value: (sample) => sample.grid_watts,
            },
          ],
          zeroBaseline: true,
          formatLabel: (value) => `${Math.round(value)} W`,
          formatTime: fmtTime,
        });

        renderLineChart(ampsChartId, samples, {
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
        });
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
