from __future__ import annotations

from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, Event
from .coordinator import LightCoordinator

from .const import *

async def async_setup_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Set up from a config entry."""
    LOGGER.debug("Config Entry Setup started")

    hass.data.setdefault(DOMAIN, {})
    coordinator = LightCoordinator(hass, entry.entry_id, entry.data)
    hass.data[DOMAIN][entry.entry_id] = coordinator

    # Initialize the device (resolves hostname, opens UDP socket, sends AUTO_HEX)
    # before we forward the entry to the light platform so the entity is ready
    # to use immediately rather than after a 30s scheduled refresh.
    await coordinator.async_config_entry_first_refresh()

    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    entry.async_on_unload(entry.add_update_listener(_async_update_listener))

    return True

async def async_unload_entry(hass: HomeAssistant, entry: ConfigEntry) -> bool:
    """Unload a config entry."""
    unload_ok = await hass.config_entries.async_unload_platforms(entry, PLATFORMS)
    if unload_ok:
        coordinator = hass.data[DOMAIN].pop(entry.entry_id)
        coordinator.close()
    return unload_ok

async def _async_update_listener(hass: HomeAssistant, entry: ConfigEntry) -> None:
    """Handle options update."""
    instance = hass.data[DOMAIN][entry.entry_id]
    if entry.title != instance.display_name:
        await hass.config_entries.async_reload(entry.entry_id)