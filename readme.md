# Ecobee Learning Integration for Home Assistant

## Overview

The Ecobee Learning Integration is a custom component for Home Assistant that provides advanced monitoring and analysis of your Ecobee thermostat's performance. This integration tracks AC runtime, learns from historical data, and alerts you to anomalous behavior, helping you optimize your HVAC system's efficiency and catch potential issues early.

## Features

- Tracks AC runtime and cooling cycles
- Stores historical data for analysis
- Calculates average runtime
- Detects anomalous behavior (when runtime exceeds 1.5 times the average)
- Provides detailed attributes including current temperature, target temperature, HVAC action, and equipment status
- Custom Lovelace dashboard for easy monitoring

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
    name: "Ecobee AC Runtime"
    climate_entity: climate.your_ecobee_entity
    db_path: "ecobee_learning.db"
```

Replace `climate.your_ecobee_entity` with the entity ID of your Ecobee thermostat in Home Assistant.

## Usage

After installation and configuration, the integration will create a new sensor entity in Home Assistant. This sensor provides the following attributes:

- `current_runtime`: Current cooling cycle runtime in minutes
- `average_runtime`: Average runtime based on historical data
- `current_temp`: Current temperature
- `target_temp`: Target temperature set on the thermostat
- `hvac_action`: Current HVAC action (cooling, idle, etc.)
- `equipment_running`: Current status of HVAC equipment
- `alert`: Boolean indicating if current runtime is anomalous

The sensor's state will be "True" when an alert is triggered (runtime exceeds 1.5 times the average) and "False" otherwise.

## Dashboard

To visualize the data from this integration, you can add the following to your Lovelace dashboard:

```yaml
title: Ecobee Learning Dashboard
views:
  - title: Ecobee Overview
    cards:
      - type: entities
        title: Ecobee Runtime Status
        entities:
          - entity: sensor.ecobee_ac_runtime
            name: AC Runtime
          - entity: sensor.ecobee_ac_runtime
            name: Average Runtime
            attribute: average_runtime
          - entity: sensor.ecobee_ac_runtime
            name: Current Temperature
            attribute: current_temp
          - entity: sensor.ecobee_ac_runtime
            name: Target Temperature
            attribute: target_temp
          - entity: sensor.ecobee_ac_runtime
            name: HVAC Action
            attribute: hvac_action
          - entity: sensor.ecobee_ac_runtime
            name: Equipment Running
            attribute: equipment_running
          - entity: sensor.ecobee_ac_runtime
            name: Alert Status
            attribute: alert

      - type: history-graph
        title: AC Runtime History
        entities:
          - entity: sensor.ecobee_ac_runtime
        hours_to_show: 24
        refresh_interval: 0

      - type: statistics-graph
        title: AC Runtime Statistics
        entities:
          - entity: sensor.ecobee_ac_runtime
        stat_types:
          - mean
          - min
          - max
        period: day

      - type: conditional
        conditions:
          - entity: sensor.ecobee_ac_runtime
            state: "True"
        card:
          type: alarm-panel
          name: AC Runtime Alert
          entity: sensor.ecobee_ac_runtime

      - type: markdown
        content: >
          This dashboard provides an overview of your Ecobee's performance based on the learning integration.
          The 'AC Runtime' shows the current runtime, while 'Average Runtime' shows the historical average.
          An alert is triggered when the current runtime significantly exceeds the average runtime.
```

## Troubleshooting

- Ensure that your Ecobee integration in Home Assistant is working correctly.
- Check the Home Assistant logs for any error messages related to the Ecobee Learning integration.
- Verify that the `climate_entity` in your configuration matches your Ecobee thermostat's entity ID in Home Assistant.
- If you're not seeing any data, ensure that your AC has run for at least one cooling cycle.

## Contributing

Contributions to improve the Ecobee Learning Integration are welcome! Please feel free to submit pull requests or open issues for bugs and feature requests.

## License

This project is licensed under the MIT License - see the [LICENSE.md](LICENSE.md) file for details.