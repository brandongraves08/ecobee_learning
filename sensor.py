import logging
import sqlite3
import aiohttp
from homeassistant.components.sensor import SensorEntity, PLATFORM_SCHEMA
from homeassistant.const import (
    PERCENTAGE,
    UnitOfTime,
    UnitOfTemperature,
)

from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import Entity
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.helpers.entity_platform import AddEntitiesCallback
import homeassistant.helpers.config_validation as cv
import voluptuous as vol
import homeassistant.util.dt as dt_util
from datetime import datetime, timedelta


DOMAIN = "ecobee_learning"

CONF_NAME = "name"
CONF_CLIMATE_ENTITY = "climate_entity"
CONF_DB_PATH = "db_path"
CONF_ENERGY_RATE = "energy_rate"
CONF_WEATHER_API_KEY = "weather_api_key"
CONF_ZIP_CODE = "zip_code"

_LOGGER = logging.getLogger(__name__)

DEFAULT_NAME = "Ecobee AC Runtime"
DEFAULT_DB_PATH = "ecobee_learning.db"
DEFAULT_ENERGY_RATE = 0.12  # $/kWh

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_CLIMATE_ENTITY): cv.entity_id,
    vol.Optional(CONF_DB_PATH, default=DEFAULT_DB_PATH): cv.string,
    vol.Optional(CONF_ENERGY_RATE, default=DEFAULT_ENERGY_RATE): cv.positive_float,
    vol.Required(CONF_WEATHER_API_KEY): cv.string,
    vol.Required(CONF_ZIP_CODE): cv.string,
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
    zip_code = config.get(CONF_ZIP_CODE)

    data = EcobeeLearningData(hass, climate_entity, db_path, energy_rate, weather_api_key, zip_code)
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

    def __init__(self, hass, climate_entity, db_path, energy_rate, weather_api_key, zip_code):
        """Initialize the data object."""
        self.hass = hass
        self.climate_entity = climate_entity
        self.db_path = db_path or DEFAULT_DB_PATH
        self.energy_rate = energy_rate or DEFAULT_ENERGY_RATE
        self.weather_api_key = weather_api_key
        self.zip_code = zip_code
        self.conn = sqlite3.connect(self.db_path)
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

            # Update calculated fields
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
        """Calculate efficiency score based on runtime and temperature change rate."""
        try:
            # Get average runtime and temp change rate for the last week
            cursor = self.conn.cursor()
            cursor.execute('''
            SELECT AVG(runtime/temp_change) as efficiency
            FROM runtime_data 
            WHERE timestamp > datetime('now', '-7 days')
            AND temp_change != 0
            ''')
            result = cursor.fetchone()
            
            if result[0] is None:
                return None
                
            # Lower minutes per degree is more efficient
            base_score = 100
            efficiency = result[0]  # minutes per degree
            
            # Adjust score based on outdoor temperature impact
            if self.data.get('outdoor_temp'):
                outdoor_temp = self.data['outdoor_temp']
                # Harder to cool when it's hotter outside, so adjust score up
                if outdoor_temp > 85:
                    base_score += 10
                elif outdoor_temp > 95:
                    base_score += 20
            
            # Penalize score based on efficiency (higher minutes per degree)
            if efficiency > 30:  # Takes more than 30 mins per degree
                base_score -= 30
            elif efficiency > 20:
                base_score -= 20
            elif efficiency > 10:
                base_score -= 10
                
            return max(0, min(100, base_score))  # Keep score between 0-100
            
        except Exception as e:
            _LOGGER.error(f"Error calculating efficiency score: {e}")
            return None

    def estimate_daily_cost(self):

        """Estimate daily energy cost based on runtime and energy rate."""
        if self.data['average_runtime']:
            daily_runtime = self.data['average_runtime'] * 24  # Assuming similar runtime over 24 hours
            return round(daily_runtime * self.energy_rate / 1000, 2)  # kWh cost
        return None

    async def get_outdoor_temperature(self):
        """Get the current outdoor temperature using the provided ZIP code."""
        if self.weather_api_key and self.zip_code:
            url = f"http://api.weatherapi.com/v1/current.json?key={self.weather_api_key}&q={self.zip_code}"
            try:
                async with aiohttp.ClientSession() as session:
                    async with session.get(url) as response:
                        response.raise_for_status()
                        data = await response.json()
                        return data['current']['temp_f']
            except Exception as e:
                _LOGGER.error(f"Error retrieving outdoor temperature: {e}")

                return None
        return None

class EcobeeRuntimeSensor(SensorEntity):
    """Representation of an Ecobee Runtime Sensor."""

    _attr_unit_of_measurement = UnitOfTime.MINUTES

    def __init__(self, name, data_key, data):
        """Initialize the sensor."""
        self._attr_name = name
        self.data_key = data_key
        self.data = data

    async def async_update(self):
        """Update the sensor."""
        await self.data.async_update()
        self._attr_state = self.data.data.get(self.data_key)

class EcobeeTemperatureSensor(SensorEntity):
    """Representation of an Ecobee Temperature Sensor."""

    _attr_unit_of_measurement = UnitOfTemperature.FAHRENHEIT

    def __init__(self, name, data_key, data):
        """Initialize the sensor."""
        self._attr_name = name
        self.data_key = data_key
        self.data = data

    async def async_update(self):
        """Update the sensor."""
        await self.data.async_update()
        self._attr_state = self.data.data.get(self.data_key)

class EcobeeStateSensor(SensorEntity):
    """Representation of an Ecobee State Sensor."""

    def __init__(self, name, data_key, data):
        """Initialize the sensor."""
        self._attr_name = name
        self.data_key = data_key
        self.data = data

    async def async_update(self):
        """Update the sensor."""
        await self.data.async_update()
        self._attr_state = self.data.data.get(self.data_key)

class EcobeeBooleanSensor(SensorEntity):
    """Representation of an Ecobee Boolean Sensor."""

    def __init__(self, name, data_key, data):
        """Initialize the sensor."""
        self._attr_name = name
        self.data_key = data_key
        self.data = data

    async def async_update(self):
        """Update the sensor."""
        await self.data.async_update()
        self._attr_state = self.data.data.get(self.data_key)
        self._attr_icon = "mdi:alert" if self._attr_state else "mdi:check"

class EcobeeEfficiencySensor(SensorEntity):
    """Representation of an Ecobee Efficiency Sensor."""

    _attr_unit_of_measurement = PERCENTAGE

    def __init__(self, name, data_key, data):
        """Initialize the sensor."""
        self._attr_name = name
        self.data_key = data_key
        self.data = data

    async def async_update(self):
        """Update the sensor."""
        await self.data.async_update()
        self._attr_state = self.data.data.get(self.data_key)

class EcobeeCostSensor(SensorEntity):
    """Representation of an Ecobee Cost Sensor."""

    _attr_unit_of_measurement = "$"

    def __init__(self, name, data_key, data):
        """Initialize the sensor."""
        self._attr_name = name
        self.data_key = data_key
        self.data = data

    async def async_update(self):
        """Update the sensor."""
        await self.data.async_update()
        self._attr_state = self.data.data.get(self.data_key)















