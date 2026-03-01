from pathlib import Path

from dagster import Definitions, definitions, load_from_defs_folder

from crypto_elt_pipeline.defs import sensors as monitoring_sensors
from crypto_elt_pipeline.defs.schedules import schedules, sensors


@definitions
def defs() -> Definitions:
    """Load all Dagster definitions including schedules and sensors."""
    base_defs = load_from_defs_folder(path_within_project=Path(__file__).parent)
    all_sensors = sensors + monitoring_sensors.sensors
    return Definitions.merge(
        base_defs,
        Definitions(schedules=schedules, sensors=all_sensors),
    )
