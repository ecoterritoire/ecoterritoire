from dataclasses import dataclass
from typing import Protocol


Measurement = dict[str, object]


@dataclass(frozen=True)
class MeasurementFilters:
    polluant: str | None = None
    zone: str | None = None
    type_mesure: str | None = None
    code_site: str | None = None
    site: str | None = None


class MeasurementRepository(Protocol):
    def find_page(
        self,
        filters: MeasurementFilters,
        offset: int,
        limit: int,
    ) -> list[Measurement]:
        """Retourne une page deja filtree par la source de donnees."""

    def find_by_id(self, measurement_id: int) -> Measurement | None:
        """Retourne une mesure ou None si elle n'existe pas."""


class InMemoryMeasurementRepository:
    """Adaptateur temporaire pour les exemples, remplacable par un adaptateur SQL."""

    def __init__(self, measurements: list[Measurement]) -> None:
        self._measurements = measurements

    def find_page(
        self,
        filters: MeasurementFilters,
        offset: int,
        limit: int,
    ) -> list[Measurement]:
        filtered = [
            measurement
            for measurement in self._measurements
            if self._matches(measurement, filters)
        ]
        return filtered[offset : offset + limit]

    def find_by_id(self, measurement_id: int) -> Measurement | None:
        return next(
            (
                measurement
                for measurement in self._measurements
                if measurement["id"] == measurement_id
            ),
            None,
        )

    @staticmethod
    def _matches(
        measurement: Measurement,
        filters: MeasurementFilters,
    ) -> bool:
        values = {
            "polluant": filters.polluant,
            "zone": filters.zone,
            "type_mesure": filters.type_mesure,
            "code_site": filters.code_site,
            "site": filters.site,
        }
        return all(
            value is None or str(measurement[tag]).lower() == value.lower()
            for tag, value in values.items()
        )