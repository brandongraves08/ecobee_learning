"""Ecobee Learning Integration for Home Assistant."""

import logging
from datetime import timedelta, datetime
import voluptuous as vol
import sqlite3
import statistics
import requests

from homeassistant.components.sensor import (
    SensorEntity,
    PLATFORM_SCHEMA
)
from homeassistant.const import (
    CONF_NAME,
    UnitOfTemperature,
    UnitOfTime,
    PERCENTAGE,
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
CONF_ENERGY_RATE = "energy_rate"
CONF_WEATHER_API_KEY = "weather_api_key"

DEFAULT_NAME = "Ecobee AC Runtime"
DEFAULT_DB_PATH = "ecobee_learning.db"
DEFAULT_ENERGY_RATE = 0.12  # $/kWh

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_CLIMATE_ENTITY): cv.entity_id,
    vol.Optional(CONF_DB_PATH, default=DEFAULT_DB_PATH): cv.string,
    vol.Optional(CONF_ENERGY_RATE, default=DEFAULT_ENERGY_RATE): cv.positive_float,
    vol.Optional(CONF_WEATHER_API_KEY): cv.string,
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
    energy_rate = config.get(CONF_ENERGY_RATE)
    weather_api_key = config.get(CONF_WEATHER_API_KEY)
    self.city = config.get('weather_city')

    data = EcobeeLearningData(hass, climate_entity, db_path, energy_rate, weather_api_key)
    await data.async_update()

    sensors = [
        EcobeeRuntimeSensor(f"{name} Current Runtime", "current_runtime", data),
        EcobeeRuntimeSensor(f"{name} Average Runtime", "average_runtime", data),
        EcobeeTemperatureSensor(f"{name} Current Temperature", "current_temp", data),
        EcobeeTemperatureSensor(f"{name} Target Temperature", "target_temp", data),
        EcobeeStateSensor(f"{name} HVAC Action", "hvac_action", data),
        EcobeeStateSensor(f"{name} Equipment Running", "equipment_running", data),
        EcobeeBooleanSensor(f"{name} Alert", "alert", data),
        EcobeeRuntimeSensor(f"{name} Avg Time per Degree", "avg_time_per_degree", data),
        EcobeeEfficiencySensor(f"{name} Energy Efficiency Score", "efficiency_score", data),
        EcobeeCostSensor(f"{name} Estimated Daily Cost", "estimated_daily_cost", data),
        EcobeeTemperatureSensor(f"{name} Outdoor Temperature", "outdoor_temp", data),
    ]

    async_add_entities(sensors, True)

class EcobeeLearningData:
    """Manage Ecobee data and historical storage."""

    def __init__(self, hass, climate_entity, db_path, energy_rate, weather_api_key):
        """Initialize the data object."""
        self.hass = hass
        self.climate_entity = climate_entity
        self.db_path = db_path
        self.energy_rate = energy_rate
        self.weather_api_key = weather_api_key
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
        (timestamp TEXT, runtime REAL, temp_change REAL, current_temp REAL, outdoor_temp REAL)
        ''')
        cursor.execute('''
        CREATE TABLE IF NOT EXISTS temp_change_rate
        (timestamp TEXT, rate REAL)
        ''')
        self.conn.commit()

    async def async_update(self):
        """Update data from Home Assistant climate entity and external sources."""
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
                outdoor_temp = await self.get_outdoor_temperature()
                self.store_data(runtime, temp_change, self.data['current_temp'], outdoor_temp)
                self.cooling_start_time = None
                self.cooling_start_temp = None

            # Update current runtime
            if self.cooling_start_time:
                self.data['current_runtime'] = (datetime.now() - self.cooling_start_time).total_seconds() / 60
            else:
                self.data['current_runtime'] = 0

            # Update other calculated fields
            self.data['average_runtime'] = self.get_average_runtime()
            self.data['alert'] = self.check_for_alert()
            self.data['avg_time_per_degree'] = self.get_avg_temp_change_rate()
            self.data['efficiency_score'] = self.calculate_efficiency_score()
            self.data['estimated_daily_cost'] = self.estimate_daily_cost()
            self.data['outdoor_temp'] = await self.get_outdoor_temperature()

    def store_data(self, runtime, temp_change, current_temp, outdoor_temp):
        """Store the runtime data in the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            INSERT INTO runtime_data (timestamp, runtime, temp_change, current_temp, outdoor_temp)
            VALUES (?, ?, ?, ?, ?)
            ''', (datetime.now().isoformat(), float(runtime), float(temp_change), float(current_temp), float(outdoor_temp)))
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

    def get_average_runtime(self):
        """Calculate average runtime from historical data."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT AVG(runtime) FROM runtime_data
            WHERE timestamp > datetime('now', '-7 days')
            ''')
            result = cursor.fetchone()
            return round(result[0], 2) if result and result[0] is not None else None
        except Exception as e:
            _LOGGER.error(f"Error calculating average runtime: {e}")
            return None

    def check_for_alert(self):
        """Check if current runtime exceeds 1.5 times the average."""
        if self.data['current_runtime'] and self.data['average_runtime']:
            return self.data['current_runtime'] > self.data['average_runtime'] * 1.5
        return False

    def get_avg_temp_change_rate(self):
        """Retrieve the average temperature change rate from the database."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT AVG(rate) FROM temp_change_rate
            WHERE timestamp > datetime('now', '-7 days')
            ''')
            result = cursor.fetchone()
            return round(result[0], 2) if result and result[0] is not None else None
        except Exception as e:
            _LOGGER.error(f"Error retrieving average temperature change rate: {e}")
            return None

    def calculate_efficiency_score(self):
        """Calculate an energy efficiency score based on runtime and temperature change."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT AVG(runtime / temp_change) FROM runtime_data
            WHERE timestamp > datetime('now', '-7 days')
            ''')
            result = cursor.fetchone()
            if result and result[0] is not None:
                # Lower values are better (less runtime per degree change)
                # Inverting and scaling to 0-100 range
                return round(100 / (1 + result[0]), 2)
            return None
        except Exception as e:
            _LOGGER.error(f"Error calculating efficiency score: {e}")
            return None

    def estimate_daily_cost(self):
        """Estimate the daily cost based on runtime and energy rate."""
        try:
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT SUM(runtime) FROM runtime_data
            WHERE timestamp > datetime('now', '-1 day')
            ''')
            result = cursor.fetchone()
            if result and result[0] is not None:
                # Assuming 3.5 kW power consumption for an average AC unit
                daily_kwh = (result[0] / 60) * 3.5
                return round(daily_kwh * self.energy_rate, 2)
            return None
        except Exception as e:
            _LOGGER.error(f"Error estimating daily cost: {e}")
            return None

    async def get_outdoor_temperature(self):
        """Fetch outdoor temperature from a weather API."""
        if not self.weather_api_key:
            return None
        
        try:
            # Replace with your preferred weather API
            url = f"http://api.openweathermap.org/data/2.5/weather?q={self.city}&appid={self.weather_api_key}&units=imperial"
            response = await self.hass.async_add_executor_job(requests.get, url)
            data = response.json()
            return data['main']['temp']
        except Exception as e:
            _LOGGER.error(f"Error fetching outdoor temperature: {e}")
            return None

class EcobeeBaseSensor(SensorEntity):
    """Base representation of an Ecobee sensor."""

    def __init__(self, name, attribute, data):
        """Initialize the sensor."""
        self._name = name
        self._attribute = attribute
        self._data = data
        self._state = None
        self._attr_unique_id = f"ecobee_learning_{data.climate_entity}_{attribute}"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def name(self):
        """Return the name of the sensor."""
        return self._name

    @property
    def state(self):
        """Return the state of the sensor."""
        return self._state

    async def async_update(self):
        """Fetch new state data for the sensor."""
        await self._data.async_update()
        self._state = self._data.data.get(self._attribute)

class EcobeeRuntimeSensor(EcobeeBaseSensor):
    """Representation of an Ecobee runtime sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfTime.MINUTES

class EcobeeTemperatureSensor(EcobeeBaseSensor):
    """Representation of an Ecobee temperature sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return UnitOfTemperature.FAHRENHEIT

class EcobeeStateSensor(EcobeeBaseSensor):
    """Representation of an Ecobee state sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return None

class EcobeeBooleanSensor(EcobeeBaseSensor):
    """Representation of an Ecobee boolean sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return None

class EcobeeEfficiencySensor(EcobeeBaseSensor):
    """Representation of an Ecobee efficiency sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return PERCENTAGE

class EcobeeCostSensor(EcobeeBaseSensor):
    """Representation of an Ecobee cost sensor."""

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement."""
        return "$"