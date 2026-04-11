"""Base entity class for Fluora Light integration."""
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN
from .coordinator import LightCoordinator


class FluoraLightBaseEntity(CoordinatorEntity[LightCoordinator]):
    """Fluora Light base entity class."""

    def __init__(self, coordinator: LightCoordinator, description: EntityDescription):
        super().__init__(coordinator)

        self.entity_description = description
        # With _attr_has_entity_name = True the entity name should only be
        # the entity-specific portion; HA prepends the device name in the UI.
        self._attr_unique_id = f"{coordinator.hostname}-{description.key}"
        self._attr_device_info = DeviceInfo(
            identifiers={(DOMAIN, coordinator.hostname)},
            name=coordinator.display_name,
            manufacturer="Fluora",
            model="Fluora Light",
            hw_version="1",
        )
