from __future__ import annotations

import logging

from api_server import create_app
from config import AppConfig
from control_loop import ControlLoop
from solar_monitor import SolarMonitor
from tesla_controller import TeslaController


def configure_logging(level: str) -> None:
    logging.basicConfig(
        level=getattr(logging, level, logging.INFO),
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )


def main() -> None:
    config = AppConfig.from_env()
    configure_logging(config.log_level)

    solar_monitor = SolarMonitor(config)
    tesla_controller = TeslaController(config)
    control_loop = ControlLoop(config, solar_monitor, tesla_controller)
    app = create_app(config, solar_monitor, tesla_controller, control_loop)

    try:
        control_loop.start()
        app.run(
            host=config.api_host,
            port=config.api_port,
            debug=False,
            use_reloader=False,
            threaded=True,
        )
    finally:
        control_loop.stop()
        tesla_controller.close()


if __name__ == "__main__":
    main()
