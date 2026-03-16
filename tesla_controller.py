from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import logging
import threading
from typing import Any

import requests
import teslapy

from config import AppConfig


LOGGER = logging.getLogger(__name__)

CONNECTED_STATES = {"Charging", "Stopped", "Complete", "Starting", "NoPower"}
DISCONNECTED_CABLES = {None, "", "<invalid>", "NoCable"}


@dataclass(slots=True)
class TeslaSnapshot:
    vehicle_name: str
    vin: str
    vehicle_state: str
    battery_percent: int | None
    charging_state: str | None
    charging_amps: int | None
    max_available_amps: int | None
    plugged_in: bool
    captured_at: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class TeslaController:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._tesla: teslapy.Tesla | None = None
        self._vehicle: dict[str, Any] | None = None
        self._last_snapshot: TeslaSnapshot | None = None
        self._last_error: str | None = None
        self._last_commanded_amps: int | None = None

    def read_status(self) -> TeslaSnapshot:
        try:
            with self._lock:
                vehicle = self._ensure_vehicle()
                vehicle.get_vehicle_summary()
                if vehicle.get("state") == "online":
                    vehicle.get_vehicle_data()

                snapshot = self._snapshot_from_vehicle(vehicle)
                self._last_snapshot = snapshot
                self._last_error = None

            LOGGER.debug("Tesla snapshot: %s", snapshot)
            return snapshot
        except Exception as exc:
            self.record_error(exc)
            raise

    def set_charging_amps(self, amps: int, source: str = "manual") -> dict[str, Any]:
        clamped_amps = max(self.config.min_amps, min(self.config.max_amps, int(amps)))
        try:
            with self._lock:
                vehicle = self._ensure_vehicle()
                vehicle.get_vehicle_summary()
                if vehicle.get("state") != "online":
                    raise RuntimeError("La Tesla n'est pas en ligne, commande ignorée")

                vehicle.get_vehicle_data()
                snapshot_before = self._snapshot_from_vehicle(vehicle)
                if not snapshot_before.plugged_in:
                    raise RuntimeError("La Tesla n'est pas branchée, commande ignorée")

                current_amps = snapshot_before.charging_amps
                if current_amps == clamped_amps or self._last_commanded_amps == clamped_amps:
                    LOGGER.info("Commande %s ignorée: %s A inchangé", source, clamped_amps)
                    return {
                        "changed": False,
                        "requested_amps": clamped_amps,
                        "current_amps": current_amps,
                        "reason": "unchanged",
                    }

                response_body = self._post_proxy_command(vehicle["vin"], clamped_amps)
                response_data = response_body.get("response", {})
                result = response_data.get("result", True)
                reason = response_data.get("reason")

                if result is False and reason != "already_set":
                    raise RuntimeError(
                        f"Commande Tesla refusée: {reason or 'raison inconnue'}"
                    )

                self._last_commanded_amps = clamped_amps
                vehicle.setdefault("charge_state", {})["charge_current_request"] = clamped_amps

                snapshot_after = self._snapshot_from_vehicle(vehicle)
                self._last_snapshot = snapshot_after
                self._last_error = None

            changed = reason != "already_set" and current_amps != clamped_amps
            LOGGER.info(
                "Commande %s envoyée: %s A pour %s",
                source,
                clamped_amps,
                snapshot_after.vehicle_name,
            )
            return {
                "changed": changed,
                "requested_amps": clamped_amps,
                "current_amps": snapshot_after.charging_amps,
                "reason": "updated" if changed else "unchanged",
                "response": response_body,
                "snapshot": snapshot_after.to_dict(),
            }
        except Exception as exc:
            self.record_error(exc)
            raise

    def get_status_payload(self) -> dict[str, Any]:
        with self._lock:
            snapshot = self._last_snapshot.to_dict() if self._last_snapshot else None
            error = self._last_error
            last_commanded_amps = self._last_commanded_amps
        return {
            "available": snapshot is not None,
            "snapshot": snapshot,
            "last_error": error,
            "last_commanded_amps": last_commanded_amps,
        }

    def close(self) -> None:
        with self._lock:
            if self._tesla is not None:
                self._tesla.close()
                self._tesla = None
                self._vehicle = None

    def record_error(self, exc: Exception) -> None:
        message = str(exc)
        with self._lock:
            self._last_error = message
        LOGGER.error("Tesla controller error: %s", message)

    def _ensure_vehicle(self) -> dict[str, Any]:
        if self._vehicle is not None:
            return self._vehicle

        if self._tesla is None:
            self._tesla = teslapy.Tesla(
                self.config.tesla_email,
                cache_file=self.config.tesla_cache_file,
                timeout=self.config.requests_timeout_seconds,
            )

        vehicles = self._tesla.vehicle_list()
        if not vehicles:
            raise RuntimeError("Aucun véhicule Tesla disponible")

        selected_vehicle = None
        if self.config.tesla_vehicle_name:
            for vehicle in vehicles:
                if vehicle.get("display_name") == self.config.tesla_vehicle_name:
                    selected_vehicle = vehicle
                    break
            if selected_vehicle is None:
                raise RuntimeError(
                    f"Véhicule Tesla introuvable: {self.config.tesla_vehicle_name}"
                )
        else:
            if self.config.tesla_vehicle_index >= len(vehicles):
                raise RuntimeError(
                    f"Index véhicule invalide: {self.config.tesla_vehicle_index}"
                )
            selected_vehicle = vehicles[self.config.tesla_vehicle_index]

        self._vehicle = selected_vehicle
        LOGGER.info("Véhicule Tesla sélectionné: %s", selected_vehicle.get("display_name"))
        return selected_vehicle

    def _snapshot_from_vehicle(self, vehicle: dict[str, Any]) -> TeslaSnapshot:
        charge_state = vehicle.get("charge_state", {})
        charging_state = charge_state.get("charging_state")
        cable = charge_state.get("conn_charge_cable")
        plugged_in = cable not in DISCONNECTED_CABLES
        if charging_state in CONNECTED_STATES:
            plugged_in = True

        return TeslaSnapshot(
            vehicle_name=vehicle.get("display_name", "Tesla"),
            vin=vehicle.get("vin", ""),
            vehicle_state=vehicle.get("state", "unknown"),
            battery_percent=self._to_optional_int(charge_state.get("battery_level")),
            charging_state=charging_state,
            charging_amps=self._to_optional_int(charge_state.get("charge_current_request")),
            max_available_amps=self._to_optional_int(
                charge_state.get("charge_current_request_max")
            ),
            plugged_in=plugged_in,
            captured_at=datetime.now(timezone.utc).isoformat(),
        )

    def _post_proxy_command(self, vin: str, amps: int) -> dict[str, Any]:
        if self._tesla is None:
            raise RuntimeError("Session Tesla non initialisée")

        access_token = self._tesla.token.get("access_token")  # type: ignore[union-attr]
        if not access_token:
            raise RuntimeError("Token Tesla indisponible")

        url = f"{self.config.tesla_proxy_url}/api/1/vehicles/{vin}/command/set_charging_amps"
        response = requests.post(
            url,
            headers={
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json",
            },
            json={"charging_amps": amps},
            timeout=self.config.requests_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Réponse Tesla proxy invalide")
        return payload

    @staticmethod
    def _to_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        return int(value)
