import logging
import time

from lib import realtime
from lib.config import settings

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)


def run() -> None:
    if settings.realtime_source == "generic" and not settings.realtime_source_url:
        raise RuntimeError("REALTIME_SOURCE_URL n'est pas configuree.")
    while True:
        try:
            measurements = realtime.fetch_measurements()
            count = realtime.publish_measurements(measurements)
            logger.info(
                "%s mesures recuperees, %s nouvelles mesures publiees",
                len(measurements),
                count,
            )
        except Exception:
            logger.exception("Echec de collecte des mesures temps reel")
        time.sleep(max(settings.realtime_poll_interval_seconds, 1))


if __name__ == "__main__":
    run()