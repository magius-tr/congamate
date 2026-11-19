"""Persistent live-map camera entity for CongaMate."""

from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import threading
import time

from homeassistant.components.camera import (
    PLATFORM_SCHEMA,
    Camera,
)
from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN
from .app.conga import Conga


PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({})

PNG_SIGNATURE = b"\x89PNG\r\n\x1a\n"

# Persist position changes at most once every two seconds.
# Full map updates are always persisted immediately.
POSITION_PERSIST_INTERVAL = 2.0


def _storage_key(serial: str) -> str:
    """Return a filesystem-safe, deterministic key for one serial."""
    return hashlib.sha256(
        serial.encode("utf-8")
    ).hexdigest()[:24]


async def async_setup_platform(
    hass,
    config,
    async_add_entities,
    discovery_info=None,
):
    """Set up one identity-ready Conga map entity."""
    if (
        "instance" not in hass.data[DOMAIN]
        or not discovery_info
    ):
        return

    serial = str(
        discovery_info["serial"]
    ).strip()

    storage_dir = Path(
        hass.config.path(
            ".storage",
            "congamate",
            _storage_key(serial),
        )
    )

    entity = CongaMapCamera(
        hass.data[DOMAIN]["instance"],
        discovery_info,
        storage_dir,
    )

    # Restore a previous snapshot, capture any map that may already
    # have arrived, and request a fresh map with listeners installed.
    await hass.async_add_executor_job(
        entity.bootstrap_map
    )

    async_add_entities([entity])


class CongaMapCamera(Camera):
    """Render and persist the most recent Conga map."""

    def __init__(
        self,
        instance: Conga,
        identity: dict,
        storage_dir: Path,
    ):
        """Initialize an identity-stable map camera."""
        super().__init__()

        self.content_type = "image/png"
        self.instance = instance

        self._serial = str(
            identity["serial"]
        ).strip()

        self._display_name = str(
            identity["name"]
        ).strip()

        self._model_snapshot = identity.get(
            "model"
        )

        self._firmware_snapshot = identity.get(
            "firmware"
        )

        self._revision_snapshot = identity.get(
            "revision"
        )

        self._attr_unique_id = (
            f"{DOMAIN}_{self._serial}_map"
        )

        self._storage_dir = storage_dir
        self._image_path = (
            storage_dir / "last_map.png"
        )
        self._metadata_path = (
            storage_dir / "last_map.json"
        )

        self._persist_lock = (
            threading.Lock()
        )

        self._persisted_image = None
        self._persisted_metadata = {}

        self._has_live_map = False
        self._last_position_persist = 0.0

        self.instance.client.on(
            "update_map",
            self._handle_map_update,
        )

        self.instance.client.on(
            "update_position",
            self._handle_position_update,
        )

        # Refresh state when the protocol connection changes.
        self.instance.client.on(
            "login",
            self._handle_connection_update,
        )

        self.instance.client.on(
            "logout",
            self._handle_connection_update,
        )

    @property
    def name(self):
        """Return current alias with stable fallback."""
        alias = str(
            self.instance.client.device.alias
            or ""
        ).strip()

        return (
            f"{alias or self._display_name} Map"
        )

    @property
    def device_info(self) -> DeviceInfo:
        """Group map and vacuum under one HA device."""
        device = self.instance.client.device

        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self._serial,
                )
            },
            name=(
                str(
                    device.alias or ""
                ).strip()
                or self._display_name
            ),
            manufacturer="Cecotec",
            model=str(
                device.model
                if device.model is not None
                else self._model_snapshot
            ),
            sw_version=(
                device.firmware_version
                or self._firmware_snapshot
            ),
            hw_version=(
                device.controller_version
                or self._revision_snapshot
            ),
        )

    @property
    def available(self):
        """Remain available while any valid map is retained."""
        return (
            self.instance.client.map.image
            is not None
            or self._persisted_image
            is not None
        )

    @property
    def extra_state_attributes(self):
        """Expose whether the displayed map is live or retained."""
        metadata = dict(
            self._persisted_metadata
        )

        live_session = bool(
            self._has_live_map
            and self.instance.is_logged
            and self.instance.is_device_connected
            and self.instance.client.socket.is_connected
        )

        return {
            "map_source": (
                "live"
                if live_session
                else "persisted"
            ),
            "map_stale": not live_session,
            "last_map_at": metadata.get(
                "updated_at"
            ),
            "last_robot_x": metadata.get(
                "robot_x"
            ),
            "last_robot_y": metadata.get(
                "robot_y"
            ),
            "last_robot_phi": metadata.get(
                "robot_phi"
            ),
            "last_charger_x": metadata.get(
                "charger_x"
            ),
            "last_charger_y": metadata.get(
                "charger_y"
            ),
            "last_state": metadata.get(
                "state"
            ),
            "last_battery_raw": metadata.get(
                "battery_raw"
            ),
            "last_fault_code": metadata.get(
                "fault_code"
            ),
        }

    def bootstrap_map(self):
        """Restore, capture and explicitly refresh the map."""
        self.restore_persisted_map()

        # DEVICE_LIST and MAP_INFO are requested close together during
        # login. A map may already be in memory before this camera entity
        # is registered and subscribes to update_map.
        if self.instance.client.map.image is not None:
            if self._persist_latest_map():
                self._has_live_map = True

        # Request a fresh snapshot after all camera callbacks have been
        # installed. This closes the startup ordering race.
        if (
            self.instance.client.socket.is_connected
            and self.instance.client.session_id
        ):
            self.instance.client.get_map_info()

    def restore_persisted_map(self):
        """Restore the last valid PNG and metadata from disk."""
        try:
            image = self._image_path.read_bytes()
        except FileNotFoundError:
            return
        except OSError:
            return

        if not image.startswith(
            PNG_SIGNATURE
        ):
            return

        metadata = {}

        try:
            metadata = json.loads(
                self._metadata_path.read_text(
                    encoding="utf-8"
                )
            )
        except (
            FileNotFoundError,
            OSError,
            ValueError,
        ):
            metadata = {}

        if not isinstance(
            metadata,
            dict,
        ):
            metadata = {}

        self._persisted_image = image
        self._persisted_metadata = metadata

    def _build_metadata(self) -> dict:
        """Build metadata for the current map snapshot."""
        device = self.instance.client.device
        conga_map = self.instance.client.map

        return {
            "schema_version": 1,
            "serial": self._serial,
            "updated_at": datetime.now(
                timezone.utc
            ).isoformat(),
            "robot_x": conga_map.robot.x,
            "robot_y": conga_map.robot.y,
            "robot_phi": conga_map.robot.phi,
            "charger_x": conga_map.charger.x,
            "charger_y": conga_map.charger.y,
            "charger_phi": conga_map.charger.phi,
            "state": device.state,
            "battery_raw": (
                device.battery_level
            ),
            "fault_code": (
                device.fault_code
            ),
            "work_mode": (
                device.work_mode
            ),
            "charge_status": (
                device.charge_status
            ),
        }

    def _persist_latest_map(self) -> bool:
        """Persist the latest render atomically."""
        image = (
            self.instance.client.map.image
        )

        if (
            image is None
            or not image.startswith(
                PNG_SIGNATURE
            )
        ):
            return False

        metadata = (
            self._build_metadata()
        )

        with self._persist_lock:
            try:
                self._storage_dir.mkdir(
                    parents=True,
                    exist_ok=True,
                )

                image_tmp = (
                    self._image_path
                    .with_suffix(".png.tmp")
                )

                metadata_tmp = (
                    self._metadata_path
                    .with_suffix(".json.tmp")
                )

                image_tmp.write_bytes(
                    image
                )

                metadata_tmp.write_text(
                    json.dumps(
                        metadata,
                        ensure_ascii=False,
                        indent=2,
                    ),
                    encoding="utf-8",
                )

                image_tmp.replace(
                    self._image_path
                )

                metadata_tmp.replace(
                    self._metadata_path
                )

            except OSError:
                return False

            self._persisted_image = image
            self._persisted_metadata = (
                metadata
            )

        return True

    def _schedule_ha_update(
        self,
        *,
        refresh_image=False,
    ):
        """Transfer protocol-thread updates safely to HA."""
        if self.hass is None:
            return

        loop = self.hass.loop

        if loop.is_closed():
            return

        def update():
            if refresh_image:
                self.async_update_token()

            self.async_write_ha_state()

        try:
            loop.call_soon_threadsafe(
                update
            )
        except RuntimeError:
            return

    def _handle_map_update(self):
        """Persist and publish a newly received full map."""
        persisted = (
            self._persist_latest_map()
        )

        if persisted:
            self._has_live_map = True

        self._schedule_ha_update(
            refresh_image=True
        )

    def _handle_position_update(self):
        """Persist recent position without excessive disk writes."""
        now = time.monotonic()

        if (
            now
            - self._last_position_persist
            >= POSITION_PERSIST_INTERVAL
        ):
            self._last_position_persist = now
            self._persist_latest_map()

        self._schedule_ha_update(
            refresh_image=False
        )

    def _handle_connection_update(self):
        """Publish live/stale state after connection changes."""
        self._schedule_ha_update(
            refresh_image=False
        )

    def camera_image(
        self,
        width=None,
        height=None,
    ):
        """Return live map or the last persisted valid map."""
        live_image = (
            self.instance.client.map.image
        )

        if live_image is not None:
            return live_image

        return self._persisted_image
