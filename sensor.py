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
from homeassistant.const import (
    CONF_NAME,
    ATTR_UNIT_OF_MEASUREMENT,
    UnitOfTemperature,
    UnitOfTime,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.event import async_track_state_change
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import EntityCategory

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ecobee_learning"

CONF_CLIMATE_ENTITY = "climate_entity"
CONF_DB_PATH = "db_path"

DEFAULT_NAME = "Ecobee AC Runtime"
DEFAULT_DB_PATH = "ecobee_learning.db"

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_CLIMATE_ENTITY): cv.entity_id,
    vol.Optional(CONF_DB_PATH, default=DEFAULT_DB_PATH): cv.string,
})

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Ecobee Learning sensors."""
    name = config.get(CONF_NAME)
    climate_entity = config.get(CONF_CLIMATE_ENTITY)
    db_path = config.get(CONF_DB_PATH)

    data = EcobeeLearningData(hass, climate_entity, db_path)
    await data.async_update()

    sensor = EcobeeRuntimeSensor(name, data)
    async_add_entities([sensor], True)

class EcobeeLearningData:
    """Manage Ecobee data and historical storage."""

    def __init__(self, hass, climate_entity, db_path):
        """Initialize the data object."""
        self.hass = hass
        self.climate_entity = climate_entity
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)
        self.create_table()
        self.data = {}
        self.cooling_start_time = None
        self.cooling_start_temp = None

    def create_table(self):
        """Create the database tables if they don't exist."""
        cursor = self.conn.cursor()
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS runtime_data
        (timestamp TEXT, runtime REAL, temp_change REAL, current_temp REAL)
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS temp_change_rate
        (timestamp TEXT, rate REAL)
        ''')
        self.conn.commit()

    async def async_update(self):
        """Update data from Home Assistant climate entity."""
        climate_state = self.hass.states.get(self.climate_entity)

        if climate_state:
            self.data['current_temp'] = climate_state.attributes.get('current_temperature')
            self.data['target_temp'] = climate_state.attributes.get('temperature')
            self.data['hvac_action'] = climate_state.attributes.get('hvac_action')
            self.data['equipment_running'] = climate_state.attributes.get('equipment_running')

            if 'compCool' in self.data.get('equipment_running', '') and self.cooling_start_time is None:
                self.cooling_start_time = datetime.now()
                self.cooling_start_temp = self.data['current_temp']
            elif 'compCool' not in self.data.get('equipment_running', '') and self.cooling_start_time is not None:
                runtime = (datetime.now() - self.cooling_start_time).total_seconds() / 60
                temp_change = self.cooling_start_temp - self.data['current_temp']
                self.store_data(runtime, temp_change, self.data['current_temp'])
                self.cooling_start_time = None
                self.cooling_start_temp = None

    def store_data(self, runtime, temp_change, current_temp):
        """Store the runtime data in the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO runtime_data (timestamp, runtime, temp_change, current_temp)
            VALUES (?, ?, ?, ?)
            ''', (datetime.now().isoformat(), float(runtime), float(temp_change), float(current_temp)))
            self.conn.commit()

            # Calculate and store the rate of temperature change
            if runtime > 0 and temp_change != 0:
                rate = abs(runtime / temp_change)  # minutes per degree
                cursor.execute('''
                INSERT INTO temp_change_rate (timestamp, rate)
                VALUES (?, ?)
                ''', (datetime.now().isoformat(), rate))
                self.conn.commit()
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
            return cursor.fetchall()
        except Exception as e:
            _LOGGER.error(f"Error retrieving historical data: {e}")
            return []

    def get_avg_temp_change_rate(self):
        """Retrieve the average temperature change rate from the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT AVG(rate) FROM temp_change_rate
            WHERE timestamp > datetime('now', '-7 days')
            ''')
            result = cursor.fetchone()
            return result[0] if result and result[0] is not None else None
        except Exception as e:
            _LOGGER.error(f"Error retrieving average temperature change rate: {e}")
            return None

class EcobeeRuntimeSensor(SensorEntity):
    """Representation of an Ecobee Runtime sensor."""

    def __init__(self, name, data):
        """Initialize the sensor."""
        self._name = name
        self._data = data
        self._attributes = {}
        self._attr_unique_id = f"ecobee_learning_{data.climate_entity}"
        self._attr_device_class = "duration"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def device_info(self):
        """Return device information about this entity."""
        return {
            "identifiers": {(DOMAIN, self._data.climate_entity)},
            "name": self._name,
            "manufacturer": "Ecobee",
            "model": "Learning Sensor",
            "via_device": (DOMAIN, self._data.climate_entity),
        }

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._attributes.get('current_runtime', 0)

    @property
    def extra_state_attributes(self):
        """Return the state attributes."""
        return self._attributes

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfTime.MINUTES

    async def async_added_to_hass(self):
        """Run when entity about to be added."""
        await super().async_added_to_hass()
        
        @callback
        def sensor_state_listener(entity, old_state, new_state):
            """Handle sensor state changes."""
            self.async_schedule_update_ha_state(True)

        self.async_on_remove(
            async_track_state_change(
                self.hass, [self._data.climate_entity], sensor_state_listener
            )
        )

    async def async_update(self):
        """Get the latest data and updates the state."""
        await self._data.async_update()
        
        try:
            if self._data.cooling_start_time and 'compCool' in self._data.data.get('equipment_running', ''):
                runtime = (datetime.now() - self._data.cooling_start_time).total_seconds() / 60
                current_runtime = round(runtime, 2)
            else:
                current_runtime = 0

            history = self._data.get_historical_data()

            if len(history) > 1:
                runtimes = [float(row[1]) for row in history]
                avg_runtime = statistics.mean(runtimes)

                self._attributes['current_runtime'] = current_runtime
                self._attributes['average_runtime'] = round(avg_runtime, 2)
                self._attributes['current_temp'] = self._data.data.get('current_temp')
                self._attributes['target_temp'] = self._data.data.get('target_temp')
                self._attributes['hvac_action'] = self._data.data.get('hvac_action')
                self._attributes['equipment_running'] = self._data.data.get('equipment_running')
                self._attributes['alert'] = current_runtime > avg_runtime * 1.5 if current_runtime > 0 else False

                avg_temp_change_rate = self._data.get_avg_temp_change_rate()
                if avg_temp_change_rate:
                    self._attributes['avg_time_per_degree'] = round(avg_temp_change_rate, 2)

                if self._attributes['alert']:
                    _LOGGER.warning(f"Anomalous runtime detected! Current: {current_runtime}, Average: {avg_runtime}")
            else:
                _LOGGER.warning("Not enough historical data to make predictions yet.")
                self._attributes['current_runtime'] = current_runtime
                self._attributes['current_temp'] = self._data.data.get('current_temp')
                self._attributes['target_temp'] = self._data.data.get('target_temp')
                self._attributes['hvac_action'] = self._data.data.get('hvac_action')
                self._attributes['equipment_running'] = self._data.data.get('equipment_running')
                self._attributes['alert'] = False

        except Exception as e:
            _LOGGER.exception(f"Error updating Ecobee Learning sensor: {e}")
            self._attributes = {}