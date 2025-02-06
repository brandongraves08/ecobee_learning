# Ecobee Learning Integration

[![hacs_badge](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://github.com/custom-components/hacs)

Advanced monitoring and analysis of your Ecobee thermostat's performance.

## Features

- Runtime tracking and cycle monitoring
- Historical data analysis
- Anomaly detection
- Energy efficiency scoring
- Cost estimation
- Outdoor temperature integration
- Custom Lovelace dashboard

## Installation

1. Install via HACS:
   - Add this repository as a custom repository in HACS
   - Type: Integration
   - Click "Install"

2. Add to your `configuration.yaml`:
   ```yaml
   sensor:
     - platform: ecobee_learning
       name: "Ecobee Downstairs"
       climate_entity: climate.downstairs
       energy_rate: 0.12
   ```

3. Install Required Custom Cards (for dashboard):
   - Add `mini-graph-card` through HACS

4. Restart Home Assistant

## Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| name | string | Ecobee AC Runtime | Name prefix for sensors |
| climate_entity | string | Required | Your Ecobee entity ID |
| energy_rate | float | 0.12 | Cost per kWh |
| weather_api_key | string | Optional | Weather API key |
| zip_code | string | Optional | ZIP code for weather |

## Support

- [Documentation](https://github.com/brandongraves08/ecobee_learning)
- [Issues](https://github.com/brandongraves08/ecobee_learning/issues)
