import logging
import requests
import sqlalchemy
from homeassistant.components.sensor import SensorEntity
from homeassistant.const import TEMP_CELSIUS
from homeassistant.helpers.entity import Entity
import homeassistant.util.dt as dt_util
from datetime import datetime, timedelta

_LOGGER = logging.getLogger(__name__)

class EcobeeLearningSensor(SensorEntity):
    def __init__(self, name, climate_entity, db_path, energy_rate, weather_api_key):
        self._name = name
        self._climate_entity = climate_entity
        self._db_path = db_path
        self._energy_rate = energy_rate
        self._weather_api_key = weather_api_key
        self._state = None
        self._attributes = {}
        self._last_update = None
        self._runtime_data = []
        self._avg_runtime = None
        self._efficiency_score = None
        self._estimated_daily_cost = None
        self._outdoor_temp = None

    @property
    def name(self):
        return self._name

    @property
    def state(self):
        return self._state

    @property
    def extra_state_attributes(self):
        return self._attributes

    def update(self):
        # Fetch current state from the climate entity
        climate_state = self.hass.states.get(self._climate_entity)
        if not climate_state:
            _LOGGER.error(f"Climate entity {self._climate_entity} not found")
            return

        current_temp = climate_state.attributes.get('current_temperature')
        target_temp = climate_state.attributes.get('temperature')
        hvac_action = climate_state.state
        equipment_running = hvac_action == 'cooling'

        # Update runtime data
        now = dt_util.utcnow()
        if self._last_update:
            runtime = (now - self._last_update).total_seconds() / 60.0
            if equipment_running:
                self._runtime_data.append(runtime)
        self._last_update = now

        # Calculate average runtime
        if self._runtime_data:
            self._avg_runtime = sum(self._runtime_data) / len(self._runtime_data)

        # Calculate efficiency score
        if self._avg_runtime and current_temp and target_temp:
            temp_diff = abs(current_temp - target_temp)
            if temp_diff > 0:
                self._efficiency_score = min(100, max(0, 100 - (self._avg_runtime / temp_diff)))

        # Estimate daily cost
        if self._avg_runtime:
            self._estimated_daily_cost = self._avg_runtime * self._energy_rate * 24

        # Fetch outdoor temperature
        if self._weather_api_key:
            self._outdoor_temp = self._fetch_outdoor_temp()

        # Update state and attributes
        self._state = runtime if equipment_running else 0
        self._attributes = {
            'current_runtime': runtime,
            'average_runtime': self._avg_runtime,
            'current_temp': current_temp,
            'target_temp': target_temp,
            'hvac_action': hvac_action,
            'equipment_running': equipment_running,
            'alert': self._avg_runtime and runtime > self._avg_runtime * 1.5,
            'avg_time_per_degree': self._avg_runtime / temp_diff if temp_diff > 0 else None,
            'efficiency_score': self._efficiency_score,
            'estimated_daily_cost': self._estimated_daily_cost,
            'outdoor_temp': self._outdoor_temp,
        }

    def _fetch_outdoor_temp(self):
        try:
            response = requests.get(f"http://api.openweathermap.org/data/2.5/weather?q=your_city&appid={self._weather_api_key}&units=metric")
            data = response.json()
            return data['main']['temp']
        except Exception as e:
            _LOGGER.error(f"Error fetching outdoor temperature: {e}")
            return None
