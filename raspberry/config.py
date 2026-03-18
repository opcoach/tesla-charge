from __future__ import annotations

import os
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Any


def _get_bool(name: str, default: bool) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _get_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == "":
        return default
    return int(value)


@dataclass(frozen=True, slots=True)
class AppConfig:
    envoy_url: str
    envoy_token: str
    envoy_verify_ssl: bool
    app_timezone: str
    tesla_client_id: str | None
    tesla_refresh_token_file: str
    tesla_api_base_url: str
    tesla_auth_url: str
    tesla_proxy_url: str
    tesla_proxy_verify_ssl: bool
    tesla_proxy_ca_file: str | None
    tesla_vehicle_name: str | None
    tesla_vehicle_index: int
    poll_interval_seconds: int
    idle_poll_interval_seconds: int
    tesla_status_interval_seconds: int
    tesla_proxy_retry_seconds: int
    day_active_start: str
    day_active_end: str
    api_host: str
    api_port: int
    min_amps: int
    max_amps: int
    requests_timeout_seconds: int
    log_level: str

    @classmethod
    def from_env(cls) -> "AppConfig":
        base_dir = Path(__file__).resolve().parent
        token_file = os.getenv("TESLA_REFRESH_TOKEN_FILE", "../tesla-refresh-token.json")
        token_path = Path(token_file)
        if not token_path.is_absolute():
            token_path = (base_dir / token_path).resolve()

        proxy_ca_file = os.getenv("TESLA_PROXY_CA_FILE", "").strip() or None
        proxy_ca_path = None
        if proxy_ca_file:
            proxy_ca_path = Path(proxy_ca_file)
            if not proxy_ca_path.is_absolute():
                proxy_ca_path = (base_dir / proxy_ca_path).resolve()

        envoy_token = os.getenv("ENPHASE_TOKEN", "").strip()
        tesla_client_id = os.getenv("TESLA_CLIENT_ID", "").strip() or None
        if tesla_client_id is None:
            tesla_client_id = cls._read_client_id_from_token_file(token_path)

        missing = []
        if not envoy_token:
            missing.append("ENPHASE_TOKEN")
        if missing:
            names = ", ".join(missing)
            raise ValueError(f"Variables d'environnement manquantes: {names}")

        poll_interval_seconds = max(1, _get_int("CONTROL_INTERVAL_SEC", 5))
        idle_poll_interval_seconds = max(
            poll_interval_seconds,
            _get_int("CONTROL_IDLE_INTERVAL_SEC", 900),
        )
        tesla_status_interval_seconds = max(
            poll_interval_seconds,
            _get_int("TESLA_STATUS_INTERVAL_SEC", 30),
        )
        tesla_proxy_retry_seconds = max(
            poll_interval_seconds,
            _get_int("TESLA_PROXY_RETRY_SEC", 60),
        )
        min_amps = _get_int("TESLA_MIN_AMPS", 6)
        max_amps = _get_int("TESLA_MAX_AMPS", 32)
        if min_amps < 6:
            min_amps = 6
        if max_amps < min_amps:
            max_amps = min_amps

        return cls(
            envoy_url=os.getenv(
                "ENVOY_URL",
                "https://192.168.68.57/ivp/meters/readings",
            ).rstrip("/"),
            envoy_token=envoy_token,
            envoy_verify_ssl=_get_bool("ENVOY_VERIFY_SSL", False),
            app_timezone=os.getenv("APP_TIMEZONE", "Europe/Paris").strip() or "Europe/Paris",
            tesla_client_id=tesla_client_id,
            tesla_refresh_token_file=str(token_path),
            tesla_api_base_url=os.getenv(
                "TESLA_API_BASE_URL",
                "https://fleet-api.prd.eu.vn.cloud.tesla.com",
            ).rstrip("/"),
            tesla_auth_url=os.getenv(
                "TESLA_AUTH_URL",
                "https://fleet-auth.prd.vn.cloud.tesla.com/oauth2/v3/token",
            ).rstrip("/"),
            tesla_proxy_url=os.getenv("TESLA_PROXY_URL", "https://localhost:4443").rstrip("/"),
            tesla_proxy_verify_ssl=_get_bool("TESLA_PROXY_VERIFY_SSL", False),
            tesla_proxy_ca_file=str(proxy_ca_path) if proxy_ca_path else None,
            tesla_vehicle_name=os.getenv("TESLA_VEHICLE_NAME") or None,
            tesla_vehicle_index=max(0, _get_int("TESLA_VEHICLE_INDEX", 0)),
            poll_interval_seconds=poll_interval_seconds,
            idle_poll_interval_seconds=idle_poll_interval_seconds,
            tesla_status_interval_seconds=tesla_status_interval_seconds,
            tesla_proxy_retry_seconds=tesla_proxy_retry_seconds,
            day_active_start=os.getenv("DAY_ACTIVE_START", "07:00").strip() or "07:00",
            day_active_end=os.getenv("DAY_ACTIVE_END", "22:00").strip() or "22:00",
            api_host=os.getenv("APP_HOST", "0.0.0.0"),
            api_port=_get_int("APP_PORT", 8080),
            min_amps=min_amps,
            max_amps=max_amps,
            requests_timeout_seconds=max(3, _get_int("REQUEST_TIMEOUT_SEC", 10)),
            log_level=os.getenv("LOG_LEVEL", "INFO").upper(),
        )

    @staticmethod
    def _read_client_id_from_token_file(path: Path) -> str | None:
        if not path.is_file():
            return None

        try:
            with path.open(encoding="utf-8") as infile:
                payload: Any = json.load(infile)
        except (OSError, ValueError):
            return None

        if not isinstance(payload, dict):
            return None

        client_id = payload.get("client_id")
        if isinstance(client_id, str) and client_id.strip():
            return client_id.strip()
        return None
