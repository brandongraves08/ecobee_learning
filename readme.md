# Ecobee Learning Integration for Home Assistant

## Overview

The Ecobee Learning Integration is a custom component for Home Assistant that provides advanced monitoring and analysis of your Ecobee thermostat's performance. This integration tracks AC runtime, learns from historical data, alerts you to anomalous behavior, calculates energy efficiency, estimates costs, and provides insights based on outdoor temperature data.

## Features

- Tracks AC runtime and cooling cycles
- Stores historical data for analysis
- Calculates average runtime
- Detects anomalous behavior (when runtime exceeds 1.5 times the average)
- Calculates the average time it takes to change temperature by one degree
- Provides an energy efficiency score based on system performance
- Estimates daily energy costs
- Fetches and incorporates outdoor temperature data (optional)
- Provides detailed attributes including current temperature, target temperature, HVAC action, and equipment status
- Custom Lovelace dashboard for easy monitoring
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

Replace `climate.downstairs` and `climate.upstairs` with the entity IDs of your Ecobee thermostats in Home Assistant.

2. Create or edit the `secrets.yaml` file in the same directory as your `configuration.yaml` and add the following:

```yaml
openweathermap_api_key: "your_actual_api_key_here"
ecobee_energy_rate: 0.12
```

Replace `"your_actual_api_key_here"` with your actual OpenWeatherMap API key, and adjust the energy rate to match your local electricity costs.

3. Make sure your `secrets.yaml` file is included in your `.gitignore` file if you're using version control, to avoid accidentally sharing your API key publicly.

4. Restart Home Assistant to apply these changes.

### Getting an OpenWeatherMap API Key

To get an OpenWeatherMap API key:

1. Go to https://openweathermap.org/ and sign up for a free account.
2. Once logged in, go to your account dashboard.
3. Look for "API keys" and generate a new key.
4. Copy this key and use it in your `secrets.yaml` file as shown above.

Note: The free tier of OpenWeatherMap has usage limits, but it should be more than sufficient for this integration's needs.

## Usage

After installation and configuration, the integration will create new sensor entities in Home Assistant. These sensors provide the following attributes:

- `current_runtime`: Current cooling cycle runtime in minutes
- `average_runtime`: Average runtime based on historical data
- `current_temp`: Current temperature
- `target_temp`: Target temperature set on the thermostat
- `hvac_action`: Current HVAC action (cooling, idle, etc.)
- `equipment_running`: Current status of HVAC equipment
- `alert`: Boolean indicating if current runtime is anomalous
- `avg_time_per_degree`: Average time it takes to change the temperature by one degree
- `efficiency_score`: Energy efficiency score (0-100) based on system performance
- `estimated_daily_cost`: Estimated daily cost of AC operation
- `outdoor_temp`: Current outdoor temperature (if weather API key is provided)

The sensor's state will be the current runtime when the system is cooling, and 0 when it's not.

## Dashboard

A custom Lovelace dashboard is provided to visualize the data from this integration. The dashboard includes:

- Runtime status for each thermostat
- Temperature and runtime history graphs
- Energy efficiency score displayed as both a trend graph and a gauge
- Estimated daily cost trend
- Conditional cards that appear when anomalies are detected

To add the dashboard, copy the provided YAML configuration into a new dashboard in your Home Assistant Lovelace UI.

## Troubleshooting

- Ensure that your Ecobee integration in Home Assistant is working correctly.
- Check the Home Assistant logs for any error messages related to the Ecobee Learning integration.
- Verify that the `climate_entity` in your configuration matches your Ecobee thermostat's entity ID in Home Assistant.
- If you're not seeing any data, ensure that your AC has run for at least one cooling cycle.
- The energy efficiency score and cost estimates require multiple cooling cycles to provide accurate data. Give it some time to collect sufficient data.
- If outdoor temperature data is not appearing, check that your OpenWeatherMap API key is correct and that you have an active internet connection.
- Make sure your `secrets.yaml` file is properly formatted and contains the correct API key and energy rate.
- If you've made changes to the configuration, always remember to restart Home Assistant.

## Contributing

Contributions to improve the Ecobee Learning Integration are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.