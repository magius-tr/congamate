"""Vacuum entity for CongaMate."""

# pylint: disable=unused-argument

from functools import partial

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumEntityFeature,
)
from homeassistant.helpers.entity import DeviceInfo

from . import DOMAIN
from .app.conga import Conga
from .app.const import (
    FAN_MODE_ECO,
    FAN_MODE_NONE,
    FAN_MODE_NORMAL,
    FAN_MODE_TURBO,
    MODEL_NAME,
)

MAX_BATTERY = 200


async def async_setup_platform(
    hass,
    config,
    async_add_entities,
    discovery_info=None,
):
    """Set up one identity-ready Conga vacuum."""
    if (
        "instance" not in hass.data[DOMAIN]
        or not discovery_info
    ):
        return

    async_add_entities(
        [
            CongaVacuum(
                hass.data[DOMAIN]["instance"],
                discovery_info,
            )
        ]
    )


class CongaVacuum(StateVacuumEntity):
    """CongaMate vacuum entity."""

    _attr_should_poll = False

    def __init__(
        self,
        instance: Conga,
        identity: dict,
    ) -> None:
        """Initialize an identity-stable vacuum."""
        super().__init__()

        self.instance = instance

        self._serial = str(
            identity["serial"]
        )

        self._display_name = str(
            identity["name"]
        )

        self._model_snapshot = (
            identity.get("model")
        )

        self._firmware_snapshot = (
            identity.get("firmware")
        )

        self._revision_snapshot = (
            identity.get("revision")
        )

        self._attr_unique_id = (
            f"{DOMAIN}_{self._serial}_vacuum"
        )

        self.instance.client.on(
            "update_device",
            self._handle_update_device,
        )

    def _handle_update_device(self):
        """Transfer a protocol-thread update to HA safely."""
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

    @property
    def name(self):
        """Return current alias, preserving the identity snapshot."""
        alias = str(
            self.instance.client.device.alias
            or ""
        ).strip()

        return alias or self._display_name

    @property
    def device_info(self) -> DeviceInfo:
        """Group vacuum and map under one HA device."""
        device = self.instance.client.device

        model = (
            MODEL_NAME.get(
                device.model,
                device.model,
            )
            if device.model is not None
            else self._model_snapshot
        )

        firmware = (
            device.firmware_version
            or self._firmware_snapshot
        )

        revision = (
            device.controller_version
            or self._revision_snapshot
        )

        return DeviceInfo(
            identifiers={
                (
                    DOMAIN,
                    self._serial,
                )
            },
            name=self.name,
            manufacturer="Cecotec",
            model=str(model),
            sw_version=firmware,
            hw_version=revision,
        )

    @property
    def available(self):
        """Report availability from the live session."""
        return bool(
            self.instance.is_running
            and self.instance.is_logged
            and self.instance.is_device_connected
            and self.instance.client.socket.is_connected
        )

    @property
    def state(self):
        return self.instance.client.device.state

    @property
    def status(self):
        if self.instance.client.device.charge_status:
            return "charging"

        return self.instance.client.device.state

    @property
    def state_attributes(self):
        data = super().state_attributes

        device = self.instance.client.device
        conga_map = self.instance.client.map

        data["clean_mode"] = device.clean_mode

        data["robot_x"] = conga_map.robot.x
        data["robot_y"] = conga_map.robot.y
        data["robot_phi"] = conga_map.robot.phi

        data["charger_x"] = conga_map.charger.x
        data["charger_y"] = conga_map.charger.y
        data["charger_phi"] = conga_map.charger.phi

        data["clean_time"] = device.clean_time
        data["clean_size"] = device.clean_size

        data["raw_type"] = device.type
        data["raw_work_mode"] = device.work_mode
        data["raw_charge_status"] = device.charge_status
        data["raw_fault_code"] = device.fault_code
        data["raw_dust_box_type"] = device.dust_box_type
        data["raw_battery_level"] = device.battery_level

        data["name"] = (
            device.alias
            or self._display_name
        )

        data["serial"] = self._serial

        data["model"] = (
            MODEL_NAME.get(
                device.model,
                device.model,
            )
            if device.model is not None
            else self._model_snapshot
        )

        data["revision"] = (
            device.controller_version
            or self._revision_snapshot
        )

        data["firmware"] = (
            device.firmware_version
            or self._firmware_snapshot
        )

        data["registered"] = (
            device.utc_registered
        )

        return data

    @property
    def battery_level(self):
        value = (
            self.instance.client.device.battery_level
        )

        if value is None:
            return None

        return value * 100 / MAX_BATTERY

    @property
    def fan_speed(self):
        return self.instance.client.device.fan_mode

    @property
    def fan_speed_list(self):
        return [
            FAN_MODE_NONE,
            FAN_MODE_ECO,
            FAN_MODE_NORMAL,
            FAN_MODE_TURBO,
        ]

    def start(self, **kwargs):
        return self.instance.client.turn_on()

    async def async_start(self, **kwargs):
        await self.hass.async_add_executor_job(
            partial(
                self.start,
                **kwargs,
            )
        )

    def stop(self, **kwargs):
        return self.instance.client.turn_off()

    async def async_stop(self, **kwargs):
        await self.hass.async_add_executor_job(
            partial(
                self.stop,
                **kwargs,
            )
        )

    def return_to_base(self, **kwargs):
        return self.instance.client.return_home()

    def locate(self, **kwargs):
        return self.instance.client.locate()

    def set_fan_speed(
        self,
        fan_speed,
        **kwargs,
    ):
        return self.instance.client.set_fan_mode(
            fan_speed
        )

    @property
    def supported_features(self):
        return (
            VacuumEntityFeature.STOP
            | VacuumEntityFeature.RETURN_HOME
            | VacuumEntityFeature.FAN_SPEED
            | VacuumEntityFeature.STATUS
            | VacuumEntityFeature.LOCATE
            | VacuumEntityFeature.MAP
            | VacuumEntityFeature.STATE
            | VacuumEntityFeature.START
        )
