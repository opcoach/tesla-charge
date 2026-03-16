from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
import threading
from typing import Any

import requests

from config import AppConfig


requests.packages.urllib3.disable_warnings()  # type: ignore[attr-defined]

LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class SolarSnapshot:
    production_watts: int
    house_consumption_watts: int
    grid_watts: int
    export_watts: int
    import_watts: int
    captured_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SolarMonitor:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._last_snapshot: SolarSnapshot | None = None
        self._last_error: str | None = None

    def read_snapshot(self) -> SolarSnapshot:
        try:
            headers = {"Authorization": f"Bearer {self.config.envoy_token}"}
            response = requests.get(
                self.config.envoy_url,
                headers=headers,
                timeout=self.config.requests_timeout_seconds,
                verify=self.config.envoy_verify_ssl,
            )
            response.raise_for_status()

            payload = response.json()
            meters = self._extract_meters(payload)
            production_watts = self._active_power(meters, 0)
            grid_watts = self._active_power(meters, 1)

            if grid_watts < 0:
                export_watts = -grid_watts
                import_watts = 0
            else:
                export_watts = 0
                import_watts = grid_watts

            snapshot = SolarSnapshot(
                production_watts=production_watts,
                house_consumption_watts=production_watts + grid_watts,
                grid_watts=grid_watts,
                export_watts=export_watts,
                import_watts=import_watts,
                captured_at=datetime.now(timezone.utc).isoformat(),
            )

            with self._lock:
                self._last_snapshot = snapshot
                self._last_error = None

            LOGGER.debug("Solar snapshot: %s", snapshot)
            return snapshot
        except Exception as exc:
            self.record_error(exc)
            raise

    def get_status_payload(self) -> dict[str, Any]:
        with self._lock:
            snapshot = self._last_snapshot.to_dict() if self._last_snapshot else None
            error = self._last_error
        return {
            "available": snapshot is not None,
            "snapshot": snapshot,
            "last_error": error,
        }

    def record_error(self, exc: Exception) -> None:
        message = str(exc)
        with self._lock:
            self._last_error = message
        LOGGER.error("Solar monitor error: %s", message)

    @staticmethod
    def _extract_meters(payload: Any) -> list[dict[str, Any]]:
        if isinstance(payload, list):
            return payload
        if isinstance(payload, dict) and isinstance(payload.get("meters"), list):
            return payload["meters"]
        raise ValueError("Réponse Envoy inattendue: liste des compteurs introuvable")

    @staticmethod
    def _active_power(meters: list[dict[str, Any]], index: int) -> int:
        try:
            meter = meters[index]
        except IndexError as exc:
            raise ValueError(f"Compteur Envoy manquant à l'index {index}") from exc

        value = meter.get("activePower", meter.get("active_power"))
        if value is None:
            raise ValueError(f"Champ activePower absent pour le compteur {index}")
        return int(round(float(value)))
