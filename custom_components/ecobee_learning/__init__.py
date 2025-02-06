"""The Ecobee Learning Integration."""
import logging
from typing import Final

from homeassistant.core import HomeAssistant
from homeassistant.helpers.typing import ConfigType

_LOGGER = logging.getLogger(__name__)
DOMAIN: Final = "ecobee_learning"

async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up the Ecobee Learning component."""
    return True

async def async_setup_entry(hass: HomeAssistant, entry: ConfigType) -> bool:
    """Set up Ecobee Learning from a config entry."""
    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigType) -> bool:
    """Unload a config entry."""
    return True
