import logging
from homeassistant.helpers.discovery import async_load_platform

_LOGGER = logging.getLogger(__name__)

DOMAIN = "ecobee_learning"

async def async_setup(hass, config):
    hass.async_create_task(
        async_load_platform(hass, 'sensor', DOMAIN, {}, config)
    )
    return True
