from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import threading
from typing import Any

import requests

from config import AppConfig


LOGGER = logging.getLogger(__name__)

CONNECTED_STATES = {"Charging", "Stopped", "Complete", "Starting", "NoPower"}
DISCONNECTED_CABLES = {None, "", "<invalid>", "NoCable"}
ERROR_LOG_THROTTLE_SECONDS = 30


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


class TeslaCommandError(RuntimeError):
    pass


class TeslaProxyUnavailableError(TeslaCommandError):
    pass


@dataclass(slots=True)
class TokenState:
    access_token: str | None
    refresh_token: str
    expires_at: datetime | None
    expires_in: int | None
    token_type: str | None
    scope: str | None
    audience: str | None
    client_id: str | None


class TeslaController:
    def __init__(self, config: AppConfig) -> None:
        self.config = config
        self._lock = threading.Lock()
        self._vehicle: dict[str, Any] | None = None
        self._token_state: TokenState | None = None
        self._last_snapshot: TeslaSnapshot | None = None
        self._last_error: str | None = None
        self._last_commanded_amps: int | None = None
        self._last_logged_error: str | None = None
        self._last_logged_error_at: datetime | None = None

    def read_status(self) -> TeslaSnapshot:
        try:
            with self._lock:
                vehicle = self._ensure_vehicle()
                summary = self._get_vehicle_summary(vehicle["vin"])
                vehicle_data = None
                if summary.get("state") == "online":
                    vehicle_data = self._get_vehicle_data(vehicle["vin"])

                merged = self._merge_vehicle(vehicle, summary, vehicle_data)
                snapshot = self._snapshot_from_vehicle(merged)
                self._vehicle = merged
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
                summary = self._get_vehicle_summary(vehicle["vin"])
                if summary.get("state") != "online":
                    raise RuntimeError("La Tesla n'est pas en ligne, commande ignorée")

                vehicle_data = self._get_vehicle_data(vehicle["vin"])
                merged = self._merge_vehicle(vehicle, summary, vehicle_data)
                snapshot_before = self._snapshot_from_vehicle(merged)
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

                response_body = self._post_proxy_command(merged["vin"], clamped_amps)
                response_data = response_body.get("response", {})
                result = response_data.get("result", True)
                reason = response_data.get("reason")
                if result is False and reason != "already_set":
                    raise RuntimeError(
                        f"Commande Tesla refusée: {reason or 'raison inconnue'}"
                    )

                self._last_commanded_amps = clamped_amps
                merged.setdefault("charge_state", {})["charge_current_request"] = clamped_amps
                snapshot_after = self._snapshot_from_vehicle(merged)
                self._vehicle = merged
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
        return

    def record_error(self, exc: Exception) -> None:
        message = str(exc)
        with self._lock:
            self._last_error = message
            should_log = self._should_log_error(message)
        if should_log:
            LOGGER.error("Tesla controller error: %s", message)

    def _ensure_vehicle(self) -> dict[str, Any]:
        if self._vehicle is not None:
            return self._vehicle

        vehicles = self._list_vehicles()
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

        vin = selected_vehicle.get("vin")
        if not isinstance(vin, str) or not vin:
            raise RuntimeError("VIN Tesla introuvable dans la liste des véhicules")

        self._vehicle = {
            "vin": vin,
            "display_name": selected_vehicle.get("display_name", "Tesla"),
            "state": selected_vehicle.get("state", "unknown"),
            "charge_state": selected_vehicle.get("charge_state", {}),
        }
        LOGGER.info("Véhicule Tesla sélectionné: %s", self._vehicle.get("display_name"))
        return self._vehicle

    def _list_vehicles(self) -> list[dict[str, Any]]:
        payload = self._api_request("GET", "/api/1/vehicles")
        vehicles = self._unwrap_response(payload)
        if not isinstance(vehicles, list):
            raise RuntimeError("Réponse Fleet API invalide pour la liste des véhicules")
        return [vehicle for vehicle in vehicles if isinstance(vehicle, dict)]

    def _get_vehicle_summary(self, vin: str) -> dict[str, Any]:
        payload = self._api_request("GET", f"/api/1/vehicles/{vin}")
        vehicle = self._unwrap_response(payload)
        if not isinstance(vehicle, dict):
            raise RuntimeError("Réponse Fleet API invalide pour le résumé du véhicule")
        return vehicle

    def _get_vehicle_data(self, vin: str) -> dict[str, Any]:
        payload = self._api_request("GET", f"/api/1/vehicles/{vin}/vehicle_data")
        vehicle = self._unwrap_response(payload)
        if not isinstance(vehicle, dict):
            raise RuntimeError("Réponse Fleet API invalide pour vehicle_data")
        return vehicle

    def _merge_vehicle(
        self,
        base_vehicle: dict[str, Any],
        summary: dict[str, Any],
        vehicle_data: dict[str, Any] | None,
    ) -> dict[str, Any]:
        merged = dict(base_vehicle)
        merged.update(summary)
        if vehicle_data:
            merged.update(vehicle_data)
            merged["charge_state"] = vehicle_data.get(
                "charge_state",
                merged.get("charge_state", {}),
            )
        return merged

    def _snapshot_from_vehicle(self, vehicle: dict[str, Any]) -> TeslaSnapshot:
        charge_state = vehicle.get("charge_state", {})
        if not isinstance(charge_state, dict):
            charge_state = {}

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
        access_token = self._ensure_access_token()
        url = f"{self.config.tesla_proxy_url}/api/1/vehicles/{vin}/command/set_charging_amps"
        try:
            response = requests.post(
                url,
                headers={
                    "Authorization": f"Bearer {access_token}",
                    "Content-Type": "application/json",
                },
                json={"charging_amps": amps},
                timeout=self.config.requests_timeout_seconds,
            )
        except requests.ConnectionError as exc:
            raise TeslaProxyUnavailableError(
                f"Proxy de commandes Tesla indisponible sur {self.config.tesla_proxy_url}"
            ) from exc

        if response.status_code == 401:
            access_token = self._refresh_access_token(force=True)
            try:
                response = requests.post(
                    url,
                    headers={
                        "Authorization": f"Bearer {access_token}",
                        "Content-Type": "application/json",
                    },
                    json={"charging_amps": amps},
                    timeout=self.config.requests_timeout_seconds,
                )
            except requests.ConnectionError as exc:
                raise TeslaProxyUnavailableError(
                    f"Proxy de commandes Tesla indisponible sur {self.config.tesla_proxy_url}"
                ) from exc

        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Réponse Tesla proxy invalide")
        return payload

    def _api_request(self, method: str, path: str) -> Any:
        access_token = self._ensure_access_token()
        url = f"{self.config.tesla_api_base_url}{path}"
        response = requests.request(
            method,
            url,
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=self.config.requests_timeout_seconds,
        )

        if response.status_code == 401:
            access_token = self._refresh_access_token(force=True)
            response = requests.request(
                method,
                url,
                headers={"Authorization": f"Bearer {access_token}"},
                timeout=self.config.requests_timeout_seconds,
            )

        response.raise_for_status()
        return response.json()

    def _ensure_access_token(self) -> str:
        if not self.config.tesla_client_id:
            raise RuntimeError("Variable d'environnement TESLA_CLIENT_ID manquante")

        token_state = self._token_state or self._load_token_state()
        if (
            token_state.access_token
            and token_state.expires_at is not None
            and datetime.now(timezone.utc) + timedelta(seconds=60) < token_state.expires_at
        ):
            self._token_state = token_state
            return token_state.access_token

        return self._refresh_access_token(force=True)

    def _refresh_access_token(self, force: bool = False) -> str:
        token_state = self._token_state or self._load_token_state()
        if (
            not force
            and token_state.access_token
            and token_state.expires_at is not None
            and datetime.now(timezone.utc) + timedelta(seconds=60) < token_state.expires_at
        ):
            return token_state.access_token

        if not self.config.tesla_client_id:
            raise RuntimeError("Variable d'environnement TESLA_CLIENT_ID manquante")

        response = requests.post(
            self.config.tesla_auth_url,
            data={
                "grant_type": "refresh_token",
                "client_id": self.config.tesla_client_id,
                "refresh_token": token_state.refresh_token,
            },
            timeout=self.config.requests_timeout_seconds,
        )
        response.raise_for_status()
        payload = response.json()
        if not isinstance(payload, dict):
            raise RuntimeError("Réponse Tesla OAuth invalide")

        access_token = payload.get("access_token")
        refresh_token = payload.get("refresh_token")
        if not isinstance(access_token, str) or not access_token:
            raise RuntimeError("access_token absent de la réponse Tesla OAuth")
        if not isinstance(refresh_token, str) or not refresh_token:
            raise RuntimeError("refresh_token absent de la réponse Tesla OAuth")

        expires_in = self._to_optional_int(payload.get("expires_in"))
        expires_at = None
        if expires_in is not None:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expires_in)

        self._token_state = TokenState(
            access_token=access_token,
            refresh_token=refresh_token,
            expires_at=expires_at,
            expires_in=expires_in,
            token_type=self._to_optional_str(payload.get("token_type")),
            scope=self._to_optional_str(payload.get("scope")),
            audience=self._to_optional_str(payload.get("audience")) or self.config.tesla_api_base_url,
            client_id=self.config.tesla_client_id,
        )
        self._store_token_state(self._token_state)
        LOGGER.info("Token Fleet API rafraîchi avec succès")
        return access_token

    def _load_token_state(self) -> TokenState:
        token_path = Path(self.config.tesla_refresh_token_file)
        if not token_path.is_file():
            raise RuntimeError(
                f"Fichier de refresh token introuvable: {self.config.tesla_refresh_token_file}"
            )

        with token_path.open(encoding="utf-8") as infile:
            payload = json.load(infile)
        if not isinstance(payload, dict):
            raise RuntimeError("Fichier de refresh token Tesla invalide")

        refresh_token = payload.get("refresh_token")
        if not isinstance(refresh_token, str) or not refresh_token:
            raise RuntimeError("refresh_token absent du fichier Tesla")

        expires_in = self._to_optional_int(payload.get("expires_in"))
        saved_at = self._parse_timestamp(
            payload.get("saved_at")
            or payload.get("issued_at")
            or payload.get("created_at")
        )
        expires_at = None
        if saved_at is not None and expires_in is not None:
            expires_at = saved_at + timedelta(seconds=expires_in)

        token_state = TokenState(
            access_token=self._to_optional_str(payload.get("access_token")),
            refresh_token=refresh_token,
            expires_at=expires_at,
            expires_in=expires_in,
            token_type=self._to_optional_str(payload.get("token_type")),
            scope=self._to_optional_str(payload.get("scope")),
            audience=self._to_optional_str(payload.get("audience")),
            client_id=self._to_optional_str(payload.get("client_id")),
        )
        self._token_state = token_state
        return token_state

    def _store_token_state(self, token_state: TokenState) -> None:
        token_path = Path(self.config.tesla_refresh_token_file)
        token_path.parent.mkdir(parents=True, exist_ok=True)

        payload = {
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "client_id": token_state.client_id,
            "access_token": token_state.access_token,
            "refresh_token": token_state.refresh_token,
            "expires_in": token_state.expires_in,
            "scope": token_state.scope,
            "token_type": token_state.token_type,
            "audience": token_state.audience,
        }

        temp_path = token_path.with_name(f"{token_path.name}.tmp")
        with temp_path.open("w", encoding="utf-8") as outfile:
            json.dump(payload, outfile, indent=2)
        temp_path.replace(token_path)

    @staticmethod
    def _unwrap_response(payload: Any) -> Any:
        if isinstance(payload, dict) and "response" in payload:
            return payload["response"]
        return payload

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        if not isinstance(value, str) or not value:
            return None

        normalized = value.replace("Z", "+00:00")
        try:
            parsed = datetime.fromisoformat(normalized)
        except ValueError:
            return None

        if parsed.tzinfo is None:
            return parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)

    @staticmethod
    def _to_optional_int(value: Any) -> int | None:
        if value is None:
            return None
        return int(value)

    @staticmethod
    def _to_optional_str(value: Any) -> str | None:
        if not isinstance(value, str) or not value.strip():
            return None
        return value.strip()

    def _should_log_error(self, message: str) -> bool:
        now = datetime.now(timezone.utc)
        if self._last_logged_error != message:
            self._last_logged_error = message
            self._last_logged_error_at = now
            return True

        if self._last_logged_error_at is None:
            self._last_logged_error_at = now
            return True

        if now - self._last_logged_error_at >= timedelta(seconds=ERROR_LOG_THROTTLE_SECONDS):
            self._last_logged_error_at = now
            return True

        return False
