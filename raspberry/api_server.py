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
    .summary-row {
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
      <div class="pill">Régulation : <span id="loop-interval">{{ loop_interval_seconds }}</span> s</div>
      <div class="pill">Tesla : environ toutes les {{ tesla_refresh_seconds }} s</div>
      <div class="pill">Mode : <span id="schedule-mode">--</span></div>
    </div>

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
        <div class="meta-line"><span>Erreur</span><strong id="error">Aucune</strong></div>
      </article>
    </section>

    <div class="footer">
      API disponibles: <code>/solar</code>, <code>/tesla</code>, <code>/status</code>, <code>POST /tesla/amps</code>
    </div>
  </main>

  <script>
    const refreshMs = {{ refresh_ms }};

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

    function setText(id, value, className) {
      const node = document.getElementById(id);
      node.textContent = value;
      node.className = className || "";
    }

    async function refresh() {
      try {
        const response = await fetch("/status", { cache: "no-store" });
        const data = await response.json();

        const solar = data.solar.snapshot || {};
        const tesla = data.tesla.snapshot || {};
        const loop = data.loop || {};

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
        setText("vehicle-name", tesla.vehicle_name || "--");
        setText("vehicle-state", tesla.vehicle_state || "--", tesla.vehicle_state === "online" ? "state-ok" : "state-warn");
        setText("plugged-in", tesla.plugged_in ? "Oui" : "Non", tesla.plugged_in ? "state-ok" : "state-warn");
        setText("loop-interval", loop.current_interval_seconds || "--");
        setText("schedule-mode", loop.schedule_mode || "--");

        const error = loop.last_error || data.solar.last_error || data.tesla.last_error || "Aucune";
        const errorClass = error === "Aucune" ? "state-ok" : "state-error";
        setText("error", error, errorClass);
      } catch (error) {
        setText("error", error.message || "Erreur inconnue", "state-error");
      }
    }

    refresh();
    setInterval(refresh, refreshMs);
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
