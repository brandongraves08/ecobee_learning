"""Ecobee Learning Integration for Home Assistant."""

import logging
from datetime import timedelta, datetime
import voluptuous as vol
import sqlite3
import statistics

from homeassistant.components.sensor import (
    SensorEntity,
    PLATFORM_SCHEMA
)
from homeassistant.const import UnitOfTemperature, CONF_NAME
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import Throttle
import homeassistant.helpers.config_validation as cv
from homeassistant.components.ecobee import DOMAIN as ECOBEE_DOMAIN

_LOGGER = logging.getLogger(__name__)
_LOGGER.setLevel(logging.DEBUG)

DOMAIN = "ecobee_learning"

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=5)

CONF_THERMOSTAT_INDEX = "thermostat_index"
CONF_DB_PATH = "db_path"
DEFAULT_NAME = "Ecobee AC Runtime"
DEFAULT_THERMOSTAT_INDEX = 0
DEFAULT_DB_PATH = "ecobee_learning.db"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_THERMOSTAT_INDEX, default=DEFAULT_THERMOSTAT_INDEX): cv.positive_int,
    vol.Optional(CONF_DB_PATH, default=DEFAULT_DB_PATH): cv.string,
})

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Ecobee Learning sensors."""
    _LOGGER.debug("Setting up Ecobee Learning platform")
    name = config.get(CONF_NAME)
    thermostat_index = config.get(CONF_THERMOSTAT_INDEX)
    db_path = config.get(CONF_DB_PATH)
    _LOGGER.debug(f"Configuration: name={name}, thermostat_index={thermostat_index}, db_path={db_path}")

    data = EcobeeLearningData(hass, thermostat_index, db_path)
    await data.async_update()

    sensor = EcobeeRuntimeSensor(name, data)
    _LOGGER.debug(f"Adding Ecobee Learning sensor: {sensor}")
    async_add_entities([sensor], True)

class EcobeeLearningData:
    """Get the latest data from Ecobee and manage historical data."""

    def __init__(self, hass, thermostat_index, db_path):
        """Initialize the data object."""
        self.hass = hass
        self.thermostat_index = thermostat_index
        self.data = None
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.create_table()
        _LOGGER.debug(f"EcobeeLearningData initialized with thermostat_index: {thermostat_index}, db_path: {db_path}")

    def create_table(self):
        """Create the database table if it doesn't exist."""
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS runtime_data
        (timestamp TEXT, runtime REAL, temp_change REAL, outdoor_temp REAL)
        ''')
        self.conn.commit()
        _LOGGER.debug("Database table created or already exists")

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    async def async_update(self):
        """Get the latest data from Ecobee."""
        try:
            _LOGGER.debug("Attempting to fetch Ecobee data")
            ecobee = self.hass.data.get(ECOBEE_DOMAIN)
            if not ecobee:
                _LOGGER.error("Ecobee integration not found in Home Assistant data")
                return

            _LOGGER.debug(f"Ecobee object: {ecobee}")
            _LOGGER.debug(f"Ecobee object methods: {dir(ecobee)}")

            if hasattr(ecobee, 'get_thermostat'):
                data = await self.hass.async_add_executor_job(ecobee.get_thermostat, self.thermostat_index)
                _LOGGER.debug(f"Raw data from get_thermostat: {data}")
            elif hasattr(ecobee, 'thermostats'):
                data = ecobee.thermostats
                _LOGGER.debug(f"Raw data from thermostats attribute: {data}")
            else:
                _LOGGER.error("Unable to find method to fetch thermostat data")
                return

            if data:
                self.data = data[0] if isinstance(data, list) else data  # Assuming we want the first thermostat
                _LOGGER.debug(f"Processed Ecobee data: {self.data}")
            else:
                _LOGGER.warning("No data returned from Ecobee")
        except Exception as e:
            _LOGGER.exception(f"Error fetching Ecobee data: {e}")
            self.data = None

    def store_data(self, runtime, temp_change, outdoor_temp):
        """Store the runtime data in the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO runtime_data (timestamp, runtime, temp_change, outdoor_temp)
            VALUES (?, ?, ?, ?)
            ''', (datetime.now().isoformat(), float(runtime), float(temp_change), float(outdoor_temp)))
            self.conn.commit()
            _LOGGER.debug(f"Stored data: runtime={runtime}, temp_change={temp_change}, outdoor_temp={outdoor_temp}")
        except Exception as e:
            _LOGGER.error(f"Error storing data in database: {e}")

    def get_historical_data(self):
        """Retrieve historical data from the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT * FROM runtime_data
            WHERE timestamp > datetime('now', '-7 days')
            ''')
            data = cursor.fetchall()
            _LOGGER.debug(f"Retrieved {len(data)} historical data points")
            return data
        except Exception as e:
            _LOGGER.error(f"Error retrieving historical data: {e}")
            return []

class EcobeeRuntimeSensor(SensorEntity):
    """Representation of an Ecobee Runtime sensor."""

    def __init__(self, name, data):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._state = None
        self._attributes = {}
        _LOGGER.debug(f"EcobeeRuntimeSensor initialized with name: {name}")

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "minutes"

    async def async_update(self):
        """Get the latest data from Ecobee and updates the state."""
        _LOGGER.debug("Starting EcobeeRuntimeSensor update")
        await self._data.async_update()
        if self._data.data is None:
            _LOGGER.error("Failed to fetch Ecobee data")
            return

        try:
            _LOGGER.debug(f"Raw Ecobee data: {self._data.data}")
            runtime = self._data.data.get('runtime', {})
            weather = self._data.data.get('weather', {})
            
            _LOGGER.debug(f"Runtime data: {runtime}")
            _LOGGER.debug(f"Weather data: {weather}")

            current_temp = float(runtime.get('actualTemperature', 0)) / 10
            target_temp = float(runtime.get('desiredHeat', 0)) / 10
            actual_runtime = float(runtime.get('actualHeatCoolTime', 0))
            outdoor_temp = float(weather.get('temperature', 0)) / 10

            _LOGGER.debug(f"Processed temperatures - Current: {current_temp}, Target: {target_temp}, Outdoor: {outdoor_temp}")
            _LOGGER.debug(f"Actual runtime: {actual_runtime}")

            temp_change = target_temp - current_temp

            # Store the new data point
            self._data.store_data(actual_runtime, temp_change, outdoor_temp)

            # Get historical data
            history = self._data.get_historical_data()

            if len(history) > 1:
                # Simple prediction based on average
                runtimes = [float(row[1]) for row in history]
                temp_changes = [float(row[2]) for row in history]
                outdoor_temps = [float(row[3]) for row in history]

                avg_runtime = statistics.mean(runtimes)
                avg_temp_change = statistics.mean(temp_changes)
                avg_outdoor_temp = statistics.mean(outdoor_temps)

                # Simple linear adjustment
                expected_runtime = avg_runtime
                if temp_change > avg_temp_change:
                    expected_runtime *= (temp_change / avg_temp_change)
                if outdoor_temp > avg_outdoor_temp:
                    expected_runtime *= (outdoor_temp / avg_outdoor_temp)

                self._state = actual_runtime
                self._attributes['expected_runtime'] = round(expected_runtime, 2)
                self._attributes['temp_change'] = round(temp_change, 2)
                self._attributes['outdoor_temp'] = round(outdoor_temp, 2)
                self._attributes['alert'] = actual_runtime > expected_runtime * 1.5

                _LOGGER.info(f"Actual runtime: {actual_runtime}, Expected runtime: {expected_runtime}")
                if self._attributes['alert']:
                    _LOGGER.warning(f"Anomalous runtime detected! Actual: {actual_runtime}, Expected: {expected_runtime}")
            else:
                _LOGGER.warning("Not enough historical data to make predictions yet.")
                self._state = actual_runtime
                self._attributes['temp_change'] = round(temp_change, 2)
                self._attributes['outdoor_temp'] = round(outdoor_temp, 2)

        except Exception as e:
            _LOGGER.exception(f"Error updating Ecobee Learning sensor: {e}")
            self._state = None
            self._attributes = {}