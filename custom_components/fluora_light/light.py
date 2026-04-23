from typing import Any

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
    ColorMode,
    LightEntity,
    LightEntityDescription,
    LightEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant import config_entries

from .coordinator import LightCoordinator, LightState
from .entity import FluoraLightBaseEntity
from .const import *

light_description = LightEntityDescription(
    key="light",
)

async def async_setup_entry(
    hass: HomeAssistant,
    config_entry: config_entries.ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    LOGGER.info('Setting up Fluora Light entry')
    # Add device
    async_add_entities([FluoraLightEntity(hass.data[DOMAIN][config_entry.entry_id], light_description)], True)


class FluoraLightEntity(FluoraLightBaseEntity, LightEntity):
    """Representation of a Fluora Light."""

    _attr_has_entity_name = True
    _attr_supported_color_modes = {ColorMode.HS, ColorMode.BRIGHTNESS}
    _attr_supported_features = LightEntityFeature.EFFECT
    _attr_effect_list = EFFECT_LIST
    # With has_entity_name=True, name=None tells HA to use the device
    # name alone (no per-entity suffix), which matches the "1 light per
    # device" model of this integration.
    _attr_name = None

    def __init__(self, coordinator: LightCoordinator, description: LightEntityDescription) -> None:
        """Initialize a FluoraLight."""
        super().__init__(coordinator, description)

    @property
    def color_mode(self) -> ColorMode:
        """Return HS when a user colour is active, BRIGHTNESS during scenes/auto/rainbow."""
        effect = self.coordinator.state.get(LightState.EFFECT)
        if effect in SCENE_EFFECTS or effect in (EFFECT_AUTO, EFFECT_RAINBOW):
            return ColorMode.BRIGHTNESS
        return ColorMode.HS

    @property
    def hs_color(self) -> tuple[float, float] | None:
        return self.coordinator.state.get(LightState.HS_COLOR)

    @property
    def brightness(self):
        return self.coordinator.state[LightState.BRIGHTNESS]

    @property
    def effect(self) -> str | None:
        """Return the current effect."""
        return self.coordinator.state[LightState.EFFECT]

    @property
    def is_on(self) -> bool:
        return self.coordinator.state[LightState.POWER]

    async def async_turn_on(self, **kwargs: Any) -> None:
        """turn on"""
        # Always send POWER_ON — the device is fire-and-forget UDP so a
        # redundant "on" is harmless, and skipping it when we *think*
        # the light is already on causes the first toggle after HA
        # restart to be a silent no-op (coordinator defaults POWER=True).
        self.coordinator.state[LightState.POWER] = True
        self.async_write_ha_state()
        await self.coordinator.async_update_state(LightState.POWER, True)

        if ATTR_HS_COLOR in kwargs:
            await self.coordinator.async_update_state(
                LightState.HS_COLOR, kwargs[ATTR_HS_COLOR]
            )
        if ATTR_BRIGHTNESS in kwargs:
            await self.coordinator.async_update_state(
                LightState.BRIGHTNESS, kwargs[ATTR_BRIGHTNESS]
            )
        if ATTR_EFFECT in kwargs:
            await self.coordinator.async_update_state(
                LightState.EFFECT, kwargs[ATTR_EFFECT]
            )

    async def async_turn_off(self, **kwargs: Any) -> None:
        """turn off"""
        if self.is_on:
            self.coordinator.state[LightState.POWER] = False
            self.async_write_ha_state()
        await self.coordinator.async_update_state(LightState.POWER, False)
