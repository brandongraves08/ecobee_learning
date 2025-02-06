# Ecobee Learning Integration for Home Assistant

## Overview

The Ecobee Learning Integration is a custom component for Home Assistant that provides advanced monitoring and analysis of your Ecobee thermostat's performance. It uses machine learning techniques to analyze your HVAC system's performance, track energy usage, and provide intelligent insights about your system's efficiency.

## Features

### Core Functionality
- Real-time AC runtime and cooling cycle tracking
- Historical data analysis with automatic data cleanup
- Anomaly detection for unusual runtime patterns
- System performance metrics (time to change temperature)
- Energy efficiency scoring (0-100)
- Daily energy cost estimation with configurable rates
- Outdoor temperature integration via Weather API
- Support for multiple thermostats (e.g., upstairs/downstairs)

### Advanced Features
- Intelligent caching of weather data to prevent API rate limits
- Automatic database maintenance and optimization
- Configurable alert thresholds for runtime anomalies
- Precise energy cost calculations based on actual runtime
- Comprehensive error handling and recovery
- Resource-efficient operation with connection pooling

### Sensor Entities
Each thermostat creates the following sensor entities:
- Current Runtime (minutes)
- Average Runtime (minutes)
- Current Temperature (°F)
- Target Temperature (°F)
- HVAC Action Status
- Equipment Running Status
- Runtime Alert Status
- Average Time per Degree (minutes)
- Energy Efficiency Score (%)
- Estimated Daily Cost ($)
- Outdoor Temperature (°F, if configured)

## Requirements

- Home Assistant 2023.1.0 or newer
- Ecobee thermostat already integrated with Home Assistant
- Python 3.9 or newer
- Optional: Weather API key for outdoor temperature data

## Installation

1. Create the custom component directory:
   ```bash
   mkdir -p custom_components/ecobee_learning
   ```

2. Copy the following files into the new directory:
   - `__init__.py`
   - `manifest.json`
   - `sensor.py`

3. Restart Home Assistant

## Configuration

### Basic Configuration
Add to your `configuration.yaml`:

```yaml
sensor:
  - platform: ecobee_learning
    name: "Ecobee Downstairs"
    climate_entity: climate.downstairs
    energy_rate: 0.12
```

### Full Configuration
```yaml
sensor:
  - platform: ecobee_learning
    name: "Ecobee Downstairs"
    climate_entity: climate.downstairs
    db_path: "ecobee_learning_downstairs.db"  # Optional, defaults to ecobee_learning.db
    energy_rate: !secret ecobee_energy_rate
    weather_api_key: !secret weather_api_key  # Optional
    zip_code: !secret weather_zip_code        # Required if weather_api_key is provided
    alert_threshold: 1.5                      # Optional, defaults to 1.5
    weather_cache_seconds: 300                # Optional, defaults to 300 (5 minutes)
    db_cleanup_days: 30                       # Optional, defaults to 30 days
```

### Configuration Options

| Option | Type | Default | Description |
|--------|------|---------|-------------|
| name | string | Ecobee AC Runtime | Name prefix for all created sensors |
| climate_entity | string | Required | Entity ID of your Ecobee thermostat |
| db_path | string | ecobee_learning.db | Path to store the SQLite database |
| energy_rate | float | 0.12 | Cost per kWh in your area |
| weather_api_key | string | Optional | API key for weather data |
| zip_code | string | Optional | ZIP code for weather data |
| alert_threshold | float | 1.5 | Multiplier for runtime alerts |
| weather_cache_seconds | integer | 300 | Weather data cache duration |
| db_cleanup_days | integer | 30 | Days to keep historical data |

## Database Management

The integration automatically manages its SQLite database:
- Creates necessary tables and indexes
- Cleans up old data based on `db_cleanup_days` setting
- Optimizes queries with proper indexing
- Uses connection pooling for better performance

## Weather Integration

If configured with a weather API key and ZIP code:
- Fetches real-time outdoor temperature data
- Implements intelligent caching to prevent API rate limits
- Handles API errors gracefully
- Falls back to cached data when needed

## Dashboard

A custom Lovelace dashboard is provided to visualize your HVAC system's performance data. The dashboard includes:

### Main Features
- Real-time thermostat control
- Current status display (runtime, HVAC action, equipment status)
- Temperature history graphs (current, target, and outdoor)
- Runtime history visualization
- Energy efficiency score with trend analysis
- Cost analysis and statistics
- Conditional alert card for anomalous behavior
- Detailed system performance metrics

### Installation

1. Prerequisites:
   - HACS (Home Assistant Community Store)
   - Custom mini-graph-card: `custom:mini-graph-card`

2. Install Required Custom Cards:
   ```yaml
   # Through HACS
   - mini-graph-card
   ```

3. Add Dashboard:
   - Navigate to Configuration -> Lovelace Dashboards
   - Click the + button to add a new dashboard
   - Select "Start with an empty dashboard"
   - Click the three dots menu and select "Raw configuration editor"
   - Copy the contents of `dashboard.yaml` into the editor
   - Save the configuration

### Dashboard Sections

1. **Current Status**
   - Thermostat control interface
   - Current runtime display
   - HVAC and equipment status
   - Outdoor temperature

2. **Performance Metrics**
   - Temperature history graph
     - Current temperature
     - Target temperature
     - Outdoor temperature
   - Runtime history visualization
   - 24-hour historical data

3. **Efficiency Metrics**
   - Energy efficiency score gauge (0-100)
   - Weekly efficiency trend graph
   - Color-coded severity levels
     - Green: 80-100 (Excellent)
     - Yellow: 60-79 (Good)
     - Red: 0-59 (Needs Attention)

4. **Cost Analysis**
   - Daily cost estimate trend
   - Monthly statistics
     - Average daily cost
     - Minimum and maximum costs
   - Weekly cost visualization

5. **Alert System**
   - Conditional card appears when runtime is abnormal
   - Provides possible causes and suggestions
   - Visual warning indicator

6. **System Performance**
   - Minutes per degree metric
   - Average runtime statistics
   - Daily cost estimates
   - Efficiency score details

### Customization

The dashboard can be customized by editing `dashboard.yaml`:

1. Entity Names:
   - Replace `climate.ecobee_downstairs` with your thermostat entity
   - Update sensor names to match your configuration

2. Display Options:
   - Adjust `hours_to_show` for different time ranges
   - Modify `points_per_hour` for graph resolution
   - Customize color schemes and severity levels

3. Layout:
   - Rearrange cards by moving their sections in the YAML
   - Add or remove cards based on your needs
   - Modify card sizes and layouts

4. Statistics:
   - Change statistical period (day, week, month)
   - Add additional statistical metrics
   - Customize graph appearances

### Troubleshooting

1. Missing Graphs:
   - Verify custom cards are installed
   - Check entity names match your configuration
   - Ensure history is being recorded

2. Layout Issues:
   - Clear browser cache
   - Try different browsers
   - Check YAML indentation

3. Performance:
   - Adjust points_per_hour for smoother loading
   - Reduce hours_to_show if graphs are slow
   - Consider using fewer cards if performance is an issue

## Troubleshooting

### Common Issues

1. Missing Temperature Data
   - Verify your climate entity is correct
   - Check Home Assistant logs for errors
   - Ensure Ecobee integration is working

2. Weather Data Issues
   - Verify API key and ZIP code
   - Check API rate limits
   - Review Home Assistant logs

3. Performance Issues
   - Consider reducing `db_cleanup_days`
   - Adjust `weather_cache_seconds`
   - Check database size and system resources

### Debug Logging

Add to your `configuration.yaml`:
```yaml
logger:
  default: info
  logs:
    custom_components.ecobee_learning: debug
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request. For major changes:
1. Open an issue first to discuss the change
2. Update tests as appropriate
3. Update documentation to reflect changes

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- Home Assistant community for inspiration and support
- Ecobee for their excellent API
- Weather API providers for temperature data
