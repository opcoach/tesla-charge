from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from datetime import datetime, time, timezone
import logging
import threading
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from config import AppConfig
from solar_monitor import SolarMonitor, SolarSnapshot
from tesla_controller import TeslaController, TeslaProxyUnavailableError, TeslaSnapshot


LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class TimeWindow:
    start: time
    end: time

    def contains(self, current: time) -> bool:
        if self.start == self.end:
            return True
        if self.start < self.end:
            return self.start <= current < self.end
        return current >= self.start or current < self.end


@dataclass(slots=True)
class LoopStatus:
    running: bool
    poll_interval_seconds: int
    current_interval_seconds: int
    schedule_mode: str
    desired_amps: int | None
    applied_amps: int | None
    last_reason: str | None
    last_run_at: str | None
    last_success_at: str | None
    last_error: str | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ControlLoop:
    def __init__(
        self,
        config: AppConfig,
        solar_monitor: SolarMonitor,
        tesla_controller: TeslaController,
    ) -> None:
        self.config = config
        self.solar_monitor = solar_monitor
        self.tesla_controller = tesla_controller
        self._stop_event = threading.Event()
        self._thread: threading.Thread | None = None
        self._lock = threading.Lock()
        self._timezone = self._build_timezone(config.app_timezone)
        self._day_active_window = self._parse_window(
            config.day_active_start,
            config.day_active_end,
        )
        self._status = LoopStatus(
            running=False,
            poll_interval_seconds=config.poll_interval_seconds,
            current_interval_seconds=config.poll_interval_seconds,
            schedule_mode="active_day",
            desired_amps=None,
            applied_amps=None,
            last_reason=None,
            last_run_at=None,
            last_success_at=None,
            last_error=None,
        )
        self._start_candidate_since: datetime | None = None
        self._stop_candidate_since: datetime | None = None

    def start(self) -> None:
        if self._thread and self._thread.is_alive():
            return
        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run,
            name="tesla-charge-loop",
            daemon=True,
        )
        self._thread.start()
        LOGGER.info(
            "Boucle de contrôle démarrée, intervalle actif %s s, intervalle veille %s s",
            self.config.poll_interval_seconds,
            self.config.idle_poll_interval_seconds,
        )

    def stop(self) -> None:
        self._stop_event.set()
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=5)
        with self._lock:
            self._status.running = False
        LOGGER.info("Boucle de contrôle arrêtée")

    def get_status_payload(self) -> dict[str, Any]:
        with self._lock:
            loop_status = self._status.to_dict()
        return {
            "loop": loop_status,
            "solar": self.solar_monitor.get_status_payload(),
            "tesla": self.tesla_controller.get_status_payload(),
        }

    def _run(self) -> None:
        with self._lock:
            self._status.running = True

        while not self._stop_event.is_set():
            started_at = self._now()
            schedule_mode, wait_seconds = self._get_schedule_mode()
            try:
                if schedule_mode == "idle_night":
                    with self._lock:
                        self._status.running = True
                        self._status.current_interval_seconds = wait_seconds
                        self._status.schedule_mode = schedule_mode
                        self._status.last_run_at = started_at
                        self._status.last_reason = "idle_night"
                        self._status.last_error = None
                    LOGGER.debug("Boucle en veille horaire")
                    self._stop_event.wait(wait_seconds)
                    continue

                solar_snapshot = self.solar_monitor.read_snapshot()
                tesla_snapshot = self.tesla_controller.read_status()
                desired_amps = self._calculate_desired_amps(solar_snapshot, tesla_snapshot)
                decision = self._apply_decision(desired_amps, tesla_snapshot)

                with self._lock:
                    self._status.running = True
                    self._status.current_interval_seconds = wait_seconds
                    self._status.schedule_mode = schedule_mode
                    self._status.desired_amps = desired_amps
                    self._status.applied_amps = decision["applied_amps"]
                    self._status.last_reason = decision["reason"]
                    self._status.last_run_at = started_at
                    self._status.last_success_at = started_at
                    self._status.last_error = None

                LOGGER.info(
                    "Contrôle: surplus=%s W cible=%s A résultat=%s",
                    solar_snapshot.export_watts,
                    desired_amps,
                    decision["reason"],
                )
            except Exception as exc:
                with self._lock:
                    self._status.running = True
                    self._status.current_interval_seconds = wait_seconds
                    self._status.schedule_mode = schedule_mode
                    self._status.last_run_at = started_at
                    self._status.last_error = str(exc)
                    self._status.last_reason = "error"
                LOGGER.exception("Erreur dans la boucle de contrôle")

            self._stop_event.wait(wait_seconds)

    def _apply_decision(
        self,
        desired_amps: int,
        tesla_snapshot: TeslaSnapshot,
    ) -> dict[str, Any]:
        if not tesla_snapshot.plugged_in:
            self._start_candidate_since = None
            self._stop_candidate_since = None
            return {
                "applied_amps": tesla_snapshot.charging_amps,
                "reason": "vehicle_not_plugged",
            }

        if tesla_snapshot.vehicle_state != "online":
            self._start_candidate_since = None
            self._stop_candidate_since = None
            return {
                "applied_amps": tesla_snapshot.charging_amps,
                "reason": "vehicle_not_online",
            }

        now = datetime.now(timezone.utc)
        is_charging = self._is_charging(tesla_snapshot)

        if is_charging:
            self._start_candidate_since = None
            if desired_amps <= self.config.charge_stop_amps:
                if self._stop_candidate_since is None:
                    self._stop_candidate_since = now
                if not self._is_confirmed(
                    self._stop_candidate_since,
                    now,
                    self.config.charge_stop_confirm_seconds,
                ):
                    return {
                        "applied_amps": tesla_snapshot.charging_amps,
                        "reason": "stop_pending",
                    }
                self._stop_candidate_since = None
                try:
                    result = self.tesla_controller.stop_charging(source="control_loop")
                except TeslaProxyUnavailableError:
                    return {
                        "applied_amps": tesla_snapshot.charging_amps,
                        "reason": "proxy_unavailable",
                    }
                return {
                    "applied_amps": 0,
                    "reason": result.get("reason", "stopped"),
                }

            self._stop_candidate_since = None
            if tesla_snapshot.charging_amps == desired_amps:
                return {
                    "applied_amps": desired_amps,
                    "reason": "unchanged",
                }

            try:
                result = self.tesla_controller.set_charging_amps(
                    desired_amps,
                    source="control_loop",
                )
            except TeslaProxyUnavailableError:
                return {
                    "applied_amps": tesla_snapshot.charging_amps,
                    "reason": "proxy_unavailable",
                }
            return {
                "applied_amps": result.get("requested_amps"),
                "reason": result.get("reason", "updated"),
            }

        self._stop_candidate_since = None
        if desired_amps < self.config.charge_start_amps:
            self._start_candidate_since = None
            return {
                "applied_amps": tesla_snapshot.charging_amps,
                "reason": "waiting_for_surplus",
            }

        if self._start_candidate_since is None:
            self._start_candidate_since = now
        if not self._is_confirmed(
            self._start_candidate_since,
            now,
            self.config.charge_start_confirm_seconds,
        ):
            return {
                "applied_amps": tesla_snapshot.charging_amps,
                "reason": "start_pending",
            }

        self._start_candidate_since = None
        try:
            start_result = self.tesla_controller.start_charging(source="control_loop")
            desired_after_start = desired_amps
            set_result = start_result
            if desired_amps >= self.config.min_amps:
                set_result = self.tesla_controller.set_charging_amps(
                    desired_amps,
                    source="control_loop",
                )
                desired_after_start = set_result.get("requested_amps", desired_amps)
        except TeslaProxyUnavailableError:
            return {
                "applied_amps": tesla_snapshot.charging_amps,
                "reason": "proxy_unavailable",
            }
        return {
            "applied_amps": desired_after_start,
            "reason": set_result.get("reason", "started"),
        }

    @staticmethod
    def _is_charging(tesla_snapshot: TeslaSnapshot) -> bool:
        return tesla_snapshot.charging_state in {"Charging", "Starting"}

    @staticmethod
    def _is_confirmed(since: datetime, now: datetime, required_seconds: int) -> bool:
        return (now - since).total_seconds() >= required_seconds

    def _calculate_desired_amps(self, solar_snapshot: SolarSnapshot, tesla_snapshot: TeslaSnapshot) -> int:
        current_amps = tesla_snapshot.charging_amps or 0
        net_watts = solar_snapshot.export_watts - solar_snapshot.import_watts
        delta_amps = math.floor(net_watts / self.config.nominal_voltage)
        raw_amps = current_amps + delta_amps
        return max(0, min(self.config.max_amps, raw_amps))

    def _get_schedule_mode(self) -> tuple[str, int]:
        current_local_time = datetime.now(self._timezone).time()
        if self._day_active_window.contains(current_local_time):
            return "active_day", self.config.poll_interval_seconds
        return "idle_night", self.config.idle_poll_interval_seconds

    def _build_timezone(self, timezone_name: str) -> ZoneInfo:
        try:
            return ZoneInfo(timezone_name)
        except ZoneInfoNotFoundError:
            LOGGER.warning(
                "Fuseau horaire inconnu %s, utilisation de Europe/Paris",
                timezone_name,
            )
            return ZoneInfo("Europe/Paris")

    @staticmethod
    def _parse_window(start_str: str, end_str: str) -> TimeWindow:
        return TimeWindow(
            start=ControlLoop._parse_time(start_str),
            end=ControlLoop._parse_time(end_str),
        )

    @staticmethod
    def _parse_time(value: str) -> time:
        hour_str, minute_str = value.split(":", 1)
        return time(hour=int(hour_str), minute=int(minute_str))

    @staticmethod
    def _now() -> str:
        return datetime.now(timezone.utc).isoformat()
