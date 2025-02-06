import logging
import aiohttp
import aiosqlite
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from dataclasses import dataclass
from contextlib import asynccontextmanager
import pytz

from homeassistant.components.sensor import (
    SensorEntity,
    SensorDeviceClass,
    SensorStateClass,
)
from homeassistant.const import (
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
    PERCENTAGE,
    UnitOfTime,
    UnitOfTemperature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType
from homeassistant.util import dt as dt_util
from homeassistant.helpers.aiohttp_client import async_get_clientsession

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ecobee_learning"

CONF_NAME = "name"
CONF_CLIMATE_ENTITY = "climate_entity"
CONF_DB_PATH = "db_path"
CONF_ENERGY_RATE = "energy_rate"
CONF_WEATHER_API_KEY = "weather_api_key"
CONF_ZIP_CODE = "zip_code"

DEFAULT_NAME = "Ecobee AC Runtime"
DEFAULT_DB_PATH = "ecobee_learning.db"
DEFAULT_ENERGY_RATE = 0.12  # $/kWh

PLATFORM_SCHEMA = {
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Required(CONF_CLIMATE_ENTITY): cv.entity_id,
    vol.Optional(CONF_DB_PATH, default=DEFAULT_DB_PATH): cv.string,
    vol.Optional(CONF_ENERGY_RATE, default=DEFAULT_ENERGY_RATE): cv.positive_float,
    vol.Optional(CONF_WEATHER_API_KEY): cv.string,
    vol.Optional(CONF_ZIP_CODE): cv.string,
}

# Constants for configuration
WEATHER_CACHE_SECONDS = 300  # 5 minutes
DB_CLEANUP_DAYS = 30  # Keep 30 days of history
ALERT_THRESHOLD = 1.5  # Alert when runtime exceeds 1.5x average
MAX_RETRIES = 3
RETRY_DELAY = 1  # seconds

@dataclass
class EcobeeConfig:
    """Configuration settings for Ecobee Learning Integration."""
    name: str
    climate_entity: str
    db_path: str
    energy_rate: float
    weather_api_key: Optional[str] = None
    zip_code: Optional[str] = None
    alert_threshold: float = ALERT_THRESHOLD
    weather_cache_seconds: int = WEATHER_CACHE_SECONDS
    db_cleanup_days: int = DB_CLEANUP_DAYS
    
    @classmethod
    def from_dict(cls, config: dict) -> 'EcobeeConfig':
        """Create config from dictionary."""
        return cls(
            name=config.get(CONF_NAME, DEFAULT_NAME),
            climate_entity=config[CONF_CLIMATE_ENTITY],
            db_path=config.get(CONF_DB_PATH, DEFAULT_DB_PATH),
            energy_rate=config.get(CONF_ENERGY_RATE, DEFAULT_ENERGY_RATE),
            weather_api_key=config.get(CONF_WEATHER_API_KEY),
            zip_code=config.get(CONF_ZIP_CODE),
        )

    def validate(self) -> None:
        """Validate configuration values."""
        if self.weather_api_key and not self.zip_code:
            raise ValueError("ZIP code is required when weather API key is provided")
        if self.zip_code and not self.weather_api_key:
            raise ValueError("Weather API key is required when ZIP code is provided")
        if self.energy_rate <= 0:
            raise ValueError("Energy rate must be greater than 0")

async def async_setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    async_add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None
) -> None:
    """Set up the Ecobee Learning sensors."""
    ecobee_config = EcobeeConfig.from_dict(config)
    ecobee_config.validate()

    data = EcobeeLearningData(hass, ecobee_config.climate_entity, ecobee_config.db_path, ecobee_config.energy_rate, ecobee_config.weather_api_key, ecobee_config.zip_code)
    await data.async_init()

    sensors = [
        EcobeeRuntimeSensor(f"{ecobee_config.name} Current Runtime", "current_runtime", data),
        EcobeeRuntimeSensor(f"{ecobee_config.name} Average Runtime", "average_runtime", data),
        EcobeeTemperatureSensor(f"{ecobee_config.name} Current Temperature", "current_temp", data),
        EcobeeTemperatureSensor(f"{ecobee_config.name} Target Temperature", "target_temp", data),
        EcobeeStateSensor(f"{ecobee_config.name} HVAC Action", "hvac_action", data),
        EcobeeStateSensor(f"{ecobee_config.name} Equipment Running", "equipment_running", data),
        EcobeeBooleanSensor(f"{ecobee_config.name} Alert", "alert", data),
        EcobeeRuntimeSensor(f"{ecobee_config.name} Avg Time per Degree", "avg_time_per_degree", data),
        EcobeeEfficiencySensor(f"{ecobee_config.name} Energy Efficiency Score", "efficiency_score", data),
        EcobeeCostSensor(f"{ecobee_config.name} Estimated Daily Cost", "estimated_daily_cost", data),
        EcobeeTemperatureSensor(f"{ecobee_config.name} Outdoor Temperature", "outdoor_temp", data),
    ]

    async_add_entities(sensors, True)

class EcobeeLearningData:
    """Manage Ecobee data and historical storage."""

    def __init__(self, hass: HomeAssistant, climate_entity: str, db_path: str, 
                 energy_rate: float, weather_api_key: Optional[str], zip_code: Optional[str]):
        """Initialize the data object."""
        self.hass = hass
        self.climate_entity = climate_entity
        self.db_path = db_path
        self.energy_rate = energy_rate
        self.weather_api_key = weather_api_key
        self.zip_code = zip_code
        self._db = None
        self.data: Dict[str, Any] = {}
        self.cooling_start_time: Optional[datetime] = None
        self.cooling_start_temp: Optional[float] = None
        self._weather_cache: Dict[str, Any] = {}
        self._weather_cache_time: Optional[datetime] = None
        self._session = async_get_clientsession(hass)

    async def async_init(self) -> None:
        """Initialize async resources."""
        self._db = await aiosqlite.connect(self.db_path)
        await self._create_tables()
        await self._cleanup_old_data()

    async def async_close(self) -> None:
        """Close resources."""
        if self._db:
            await self._db.close()

    @asynccontextmanager
    async def _get_db(self):
        """Context manager for database access."""
        if not self._db:
            await self.async_init()
        try:
            yield self._db
        except Exception as e:
            _LOGGER.error(f"Database error: {e}")
            raise

    async def _create_tables(self) -> None:
        """Create database tables."""
        async with self._get_db() as db:
            await db.execute('''
                CREATE TABLE IF NOT EXISTS runtime_data (
                    timestamp TEXT,
                    runtime REAL,
                    temp_change REAL,
                    current_temp REAL,
                    outdoor_temp REAL
                )
            ''')
            await db.execute('''
                CREATE TABLE IF NOT EXISTS temp_change_rate (
                    timestamp TEXT,
                    rate REAL
                )
            ''')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_timestamp ON runtime_data(timestamp)')
            await db.execute('CREATE INDEX IF NOT EXISTS idx_rate_timestamp ON temp_change_rate(timestamp)')
            await db.commit()

    async def _cleanup_old_data(self) -> None:
        """Remove data older than DB_CLEANUP_DAYS."""
        cleanup_date = (datetime.now() - timedelta(days=DB_CLEANUP_DAYS)).isoformat()
        async with self._get_db() as db:
            await db.execute('DELETE FROM runtime_data WHERE timestamp < ?', (cleanup_date,))
            await db.execute('DELETE FROM temp_change_rate WHERE timestamp < ?', (cleanup_date,))
            await db.commit()

    async def async_update(self) -> None:
        """Update data from Home Assistant climate entity and external sources."""
        try:
            climate_state = self.hass.states.get(self.climate_entity)
            if not climate_state:
                _LOGGER.error(f"Climate entity {self.climate_entity} not found")
                return

            self.data['current_temp'] = climate_state.attributes.get('current_temperature')
            self.data['target_temp'] = climate_state.attributes.get('temperature')
            self.data['hvac_action'] = climate_state.attributes.get('hvac_action')
            self.data['equipment_running'] = climate_state.attributes.get('equipment_running', '')

            now = dt_util.now()
            is_cooling = 'compCool' in self.data['equipment_running']

            if is_cooling and self.cooling_start_time is None:
                self.cooling_start_time = now
                self.cooling_start_temp = self.data['current_temp']
            elif not is_cooling and self.cooling_start_time is not None:
                runtime = (now - self.cooling_start_time).total_seconds() / 60
                temp_change = self.cooling_start_temp - self.data['current_temp']
                outdoor_temp = await self._get_outdoor_temperature()
                
                if runtime > 0 and temp_change != 0:
                    await self._store_runtime_data(runtime, temp_change, self.data['current_temp'], outdoor_temp)
                
                self.cooling_start_time = None
                self.cooling_start_temp = None

            # Update current runtime and calculated fields
            self.data['current_runtime'] = (now - self.cooling_start_time).total_seconds() / 60 if self.cooling_start_time else 0
            
            # Update other metrics
            await self._update_metrics()

        except Exception as e:
            _LOGGER.error(f"Error updating data: {e}")

    async def _update_metrics(self) -> None:
        """Update all calculated metrics."""
        self.data['average_runtime'] = await self._get_average_runtime()
        self.data['alert'] = await self._check_for_alert()
        self.data['avg_time_per_degree'] = await self._get_avg_temp_change_rate()
        self.data['efficiency_score'] = await self._calculate_efficiency_score()
        self.data['estimated_daily_cost'] = await self._estimate_daily_cost()
        self.data['outdoor_temp'] = await self._get_outdoor_temperature()

    async def _store_runtime_data(self, runtime: float, temp_change: float, 
                                current_temp: float, outdoor_temp: Optional[float]) -> None:
        """Store runtime data in database."""
        try:
            async with self._get_db() as db:
                now = dt_util.now().isoformat()
                await db.execute(
                    'INSERT INTO runtime_data (timestamp, runtime, temp_change, current_temp, outdoor_temp) VALUES (?, ?, ?, ?, ?)',
                    (now, runtime, temp_change, current_temp, outdoor_temp or 0)
                )
                
                if runtime > 0 and temp_change != 0:
                    rate = abs(runtime / temp_change)
                    await db.execute(
                        'INSERT INTO temp_change_rate (timestamp, rate) VALUES (?, ?)',
                        (now, rate)
                    )
                await db.commit()
        except Exception as e:
            _LOGGER.error(f"Error storing runtime data: {e}")

    async def _get_average_runtime(self) -> Optional[float]:
        """Calculate average runtime from recent data."""
        try:
            async with self._get_db() as db:
                async with db.execute(
                    'SELECT AVG(runtime) FROM runtime_data WHERE timestamp > datetime("now", "-7 days")'
                ) as cursor:
                    result = await cursor.fetchone()
                    return round(result[0], 2) if result and result[0] is not None else None
        except Exception as e:
            _LOGGER.error(f"Error calculating average runtime: {e}")
            return None

    async def _check_for_alert(self) -> bool:
        """Check if current runtime exceeds threshold."""
        if not self.data.get('current_runtime') or not self.data.get('average_runtime'):
            return False
        return self.data['current_runtime'] > self.data['average_runtime'] * ALERT_THRESHOLD

    async def _get_avg_temp_change_rate(self) -> Optional[float]:
        """Get average temperature change rate."""
        try:
            async with self._get_db() as db:
                async with db.execute(
                    'SELECT AVG(rate) FROM temp_change_rate WHERE timestamp > datetime("now", "-7 days")'
                ) as cursor:
                    result = await cursor.fetchone()
                    return round(result[0], 2) if result and result[0] is not None else None
        except Exception as e:
            _LOGGER.error(f"Error calculating temperature change rate: {e}")
            return None

    async def _calculate_efficiency_score(self) -> Optional[float]:
        """Calculate efficiency score based on runtime and temperature change."""
        try:
            async with self._get_db() as db:
                async with db.execute('''
                    SELECT AVG(runtime/ABS(temp_change)) as efficiency
                    FROM runtime_data 
                    WHERE timestamp > datetime("now", "-7 days")
                    AND temp_change != 0
                ''') as cursor:
                    result = await cursor.fetchone()
                    if not result or result[0] is None:
                        return None
                    
                    # Convert to 0-100 scale (lower is better)
                    base_score = 100 - (result[0] * 5)  # 5 is a scaling factor
                    return max(0, min(100, base_score))
        except Exception as e:
            _LOGGER.error(f"Error calculating efficiency score: {e}")
            return None

    async def _estimate_daily_cost(self) -> Optional[float]:
        """Estimate daily energy cost."""
        try:
            if not self.data.get('average_runtime'):
                return None
            
            # Assume 3.5 kW average AC power consumption
            daily_runtime = self.data['average_runtime'] * 24  # minutes per day
            daily_kwh = (daily_runtime / 60) * 3.5  # convert to hours and multiply by kW
            return round(daily_kwh * self.energy_rate, 2)
        except Exception as e:
            _LOGGER.error(f"Error calculating daily cost: {e}")
            return None

    async def _get_outdoor_temperature(self) -> Optional[float]:
        """Get current outdoor temperature with caching."""
        if not self.weather_api_key or not self.zip_code:
            return None

        now = dt_util.now()
        if (self._weather_cache_time and 
            (now - self._weather_cache_time).total_seconds() < WEATHER_CACHE_SECONDS):
            return self._weather_cache.get('temp')

        url = f"http://api.weatherapi.com/v1/current.json?key={self.weather_api_key}&q={self.zip_code}"
        
        for attempt in range(MAX_RETRIES):
            try:
                async with self._session.get(url) as response:
                    if response.status == 200:
                        data = await response.json()
                        temp = data['current']['temp_f']
                        self._weather_cache = {'temp': temp}
                        self._weather_cache_time = now
                        return temp
                    elif response.status == 429:  # Rate limit
                        _LOGGER.warning("Weather API rate limit reached")
                        return self._weather_cache.get('temp')
                    else:
                        _LOGGER.error(f"Weather API error: {response.status}")
                        
            except Exception as e:
                _LOGGER.error(f"Weather API request failed (attempt {attempt + 1}/{MAX_RETRIES}): {e}")
                if attempt < MAX_RETRIES - 1:
                    await asyncio.sleep(RETRY_DELAY * (attempt + 1))
                    
        return self._weather_cache.get('temp')

class EcobeeSensorBase(SensorEntity):
    """Base class for Ecobee sensors."""

    def __init__(self, name: str, data_key: str, data: EcobeeLearningData):
        """Initialize the sensor."""
        self._attr_name = name
        self.data_key = data_key
        self.data = data
        self._attr_unique_id = f"ecobee_learning_{name.lower().replace(' ', '_')}"
        self._attr_should_poll = True

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return self.data_key in self.data.data

    async def async_update(self) -> None:
        """Update state."""
        await self.data.async_update()
        self._attr_native_value = self.data.data.get(self.data_key)


class EcobeeRuntimeSensor(EcobeeSensorBase):
    """Representation of an Ecobee Runtime Sensor."""
    
    _attr_device_class = SensorDeviceClass.DURATION
    _attr_native_unit_of_measurement = UnitOfTime.MINUTES
    _attr_state_class = SensorStateClass.MEASUREMENT


class EcobeeTemperatureSensor(EcobeeSensorBase):
    """Representation of an Ecobee Temperature Sensor."""
    
    _attr_device_class = SensorDeviceClass.TEMPERATURE
    _attr_native_unit_of_measurement = UnitOfTemperature.FAHRENHEIT
    _attr_state_class = SensorStateClass.MEASUREMENT


class EcobeeStateSensor(EcobeeSensorBase):
    """Representation of an Ecobee State Sensor."""
    
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_state_class = SensorStateClass.MEASUREMENT

    @property
    def options(self) -> List[str]:
        """Return the list of available options."""
        if self.data_key == 'hvac_action':
            return ['idle', 'cooling', 'heating']
        return []


class EcobeeBooleanSensor(EcobeeSensorBase):
    """Representation of an Ecobee Boolean Sensor."""
    
    _attr_device_class = SensorDeviceClass.ENUM
    _attr_options = ['True', 'False']

    @property
    def native_value(self) -> str:
        """Return the state."""
        return str(self.data.data.get(self.data_key, False))


class EcobeeEfficiencySensor(EcobeeSensorBase):
    """Representation of an Ecobee Efficiency Sensor."""
    
    _attr_device_class = SensorDeviceClass.POWER_FACTOR
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_state_class = SensorStateClass.MEASUREMENT


class EcobeeCostSensor(EcobeeSensorBase):
    """Representation of an Ecobee Cost Sensor."""
    
    _attr_device_class = SensorDeviceClass.MONETARY
    _attr_native_unit_of_measurement = "USD"
    _attr_state_class = SensorStateClass.MEASUREMENT
    
    @property
    def native_value(self) -> Optional[float]:
        """Return the state."""
        value = self.data.data.get(self.data_key)
        return round(float(value), 2) if value is not None else None

    @property
    def suggested_display_precision(self) -> int:
        """Return the suggested number of decimal places for display."""
        return 2
