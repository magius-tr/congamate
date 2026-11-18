"""Live map image entity for CongaMate."""

from homeassistant.components.camera import PLATFORM_SCHEMA, Camera

from . import DOMAIN
from .app.conga import Conga


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})


async def async_setup_platform(
    hass,
    config,
    async_add_entities,
    discovery_info=None,
):
    """Set up the CongaMate live map entity."""
    if "instance" in hass.data[DOMAIN] and discovery_info is not None:
        async_add_entities(
            [CongaMapCamera(hass.data[DOMAIN]["instance"])]
        )


class CongaMapCamera(Camera):
    """Render the live cleaning map as a Home Assistant image entity."""

    def __init__(self, instance: Conga):
        """Initialize the map image entity."""
        super().__init__()

        self.content_type = "image/png"
        self.instance = instance

        self.instance.client.on(
            "update_map",
            self._handle_map_update,
        )
        self.instance.client.on(
            "update_position",
            self._handle_map_update,
        )

    @property
    def name(self):
        """Return a map name based on the robot alias."""
        alias = self.instance.client.device.alias or "Conga"
        return f"{alias} Map"

    def _handle_map_update(self):
        """Transfer protocol-thread updates safely to Home Assistant."""
        if self.hass is None:
            return

        loop = self.hass.loop
        if loop.is_closed():
            return

        try:
            loop.call_soon_threadsafe(
                self.async_write_ha_state
            )
        except RuntimeError:
            return

    def camera_image(self, width=None, height=None):
        """Return the most recently rendered Conga map."""
        return self.instance.client.map.image
