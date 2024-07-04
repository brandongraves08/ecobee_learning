# Ecobee Learning Integration for Home Assistant

## Overview

The Ecobee Learning Integration is a custom component for Home Assistant that provides advanced monitoring and analysis of your Ecobee thermostat's performance. This integration tracks AC runtime, learns from historical data, alerts you to anomalous behavior, and calculates the efficiency of temperature changes, helping you optimize your HVAC system's efficiency and catch potential issues early.

## Features

- Tracks AC runtime and cooling cycles
- Stores historical data for analysis
- Calculates average runtime
- Detects anomalous behavior (when runtime exceeds 1.5 times the average)
- Calculates the average time it takes to change temperature by one degree
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

Add the following to your `configuration.yaml`:

```yaml
sensor:
  - platform: ecobee_learning
    name: "Ecobee AC Runtime Downstairs"
    climate_entity: climate.downstairs
    db_path: "ecobee_learning_downstairs.db"
  - platform: ecobee_learning
    name: "Ecobee AC Runtime Upstairs"
    climate_entity: climate.upstairs
    db_path: "ecobee_learning_upstairs.db"
```

Replace `climate.downstairs` and `climate.upstairs` with the entity IDs of your Ecobee thermostats in Home Assistant.

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

The sensor's state will be the current runtime when the system is cooling, and 0 when it's not.

## Dashboard

To visualize the data from this integration, you can add the provided Lovelace dashboard configuration to your Home Assistant. The dashboard includes:

- Runtime status for each thermostat
- History graphs of AC runtime
- Statistics graphs showing daily runtime patterns
- Conditional cards that appear when anomalies are detected
- Display of the average time it takes to change temperature by one degree

## Troubleshooting

- Ensure that your Ecobee integration in Home Assistant is working correctly.
- Check the Home Assistant logs for any error messages related to the Ecobee Learning integration.
- Verify that the `climate_entity` in your configuration matches your Ecobee thermostat's entity ID in Home Assistant.
- If you're not seeing any data, ensure that your AC has run for at least one cooling cycle.
- The temperature change rate calculation requires multiple cooling cycles to provide accurate data. Give it some time to collect sufficient data.

## Contributing

Contributions to improve the Ecobee Learning Integration are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.