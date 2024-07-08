# Ecobee Learning Integration for Home Assistant

## Overview

The Ecobee Learning Integration is a custom component for Home Assistant that provides advanced monitoring and analysis of your Ecobee thermostat's performance. It tracks AC runtime, learns from historical data, alerts you to anomalous behavior, calculates energy efficiency, estimates costs, and provides insights based on outdoor temperature data.

## Features

- Tracks AC runtime and cooling cycles
- Stores and analyzes historical data
- Calculates average runtime and detects anomalous behavior
- Measures system performance (time to change temperature by one degree)
- Provides an energy efficiency score (0-100)
- Estimates daily energy costs
- Incorporates outdoor temperature data (optional)
- Provides detailed attributes (current/target temperature, HVAC action, equipment status)
- Includes a custom Lovelace dashboard for easy monitoring
- Supports multiple Ecobee thermostats (e.g., upstairs and downstairs)

## Installation

1. Navigate to your Home Assistant configuration directory.
2. Create a new directory: `custom_components/ecobee_learning/`
3. Copy the following files into this new directory:
   - `__init__.py`
   - `manifest.json`
   - `sensor.py`

## Configuration

1. Add the following to your `configuration.yaml`:

```yaml
sensor:
  - platform: ecobee_learning
    name: "Ecobee Downstairs"
    climate_entity: climate.downstairs
    db_path: "ecobee_learning_downstairs.db"
    energy_rate: !secret ecobee_energy_rate
    weather_api_key: !secret openweathermap_api_key
  - platform: ecobee_learning
    name: "Ecobee Upstairs"
    climate_entity: climate.upstairs
    db_path: "ecobee_learning_upstairs.db"
    energy_rate: !secret ecobee_energy_rate
    weather_api_key: !secret openweathermap_api_key
```

Replace `climate.downstairs` and `climate.upstairs` with your Ecobee thermostat entity IDs.

2. Add to your `secrets.yaml`:

```yaml
openweathermap_api_key: "your_actual_api_key_here"
ecobee_energy_rate: 0.12
```

Replace `"your_actual_api_key_here"` with your OpenWeatherMap API key and adjust the energy rate to match your local electricity costs.

3. Ensure your `secrets.yaml` is in your `.gitignore` if using version control.

4. Restart Home Assistant to apply changes.

### Getting an OpenWeatherMap API Key

1. Sign up for a free account at https://openweathermap.org/
2. In your account dashboard, generate a new API key
3. Copy this key to your `secrets.yaml` file

Note: The free tier should be sufficient for this integration's needs.

## Usage

After setup, new sensor entities will be created with the following attributes:

- `current_runtime`: Current cooling cycle runtime (minutes)
- `average_runtime`: Average runtime based on historical data
- `current_temp`: Current temperature
- `target_temp`: Target temperature
- `hvac_action`: Current HVAC action (cooling, idle, etc.)
- `equipment_running`: Current status of HVAC equipment
- `alert`: Boolean indicating anomalous runtime
- `avg_time_per_degree`: Average time to change temperature by one degree
- `efficiency_score`: Energy efficiency score (0-100)
- `estimated_daily_cost`: Estimated daily AC operation cost
- `outdoor_temp`: Current outdoor temperature (if weather API key provided)

The sensor's state will be the current runtime when cooling, and 0 when not.

## Dashboard

A custom Lovelace dashboard is provided to visualize the data, including:

- Runtime status for each thermostat
- Temperature and runtime history graphs
- Energy efficiency score (trend graph and gauge)
- Estimated daily cost trend
- Conditional cards for anomaly detection

To add the dashboard, copy the provided YAML configuration into a new dashboard in your Home Assistant Lovelace UI.

## Troubleshooting

- Verify your Ecobee integration in Home Assistant is working correctly
- Check Home Assistant logs for error messages
- Ensure `climate_entity` in your configuration matches your Ecobee thermostat's entity ID
- Allow time for data collection (multiple cooling cycles for accurate efficiency and cost data)
- For missing outdoor temperature data, check your OpenWeatherMap API key and internet connection
- Verify `secrets.yaml` formatting and content
- Restart Home Assistant after configuration changes

## Contributing

Contributions are welcome! Please submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.