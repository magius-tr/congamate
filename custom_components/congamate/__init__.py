"""CongaMate integration."""

# pylint: disable=unused-argument

from __future__ import annotations

import asyncio
import logging
import os
from typing import Any

import voluptuous as vol

from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery

from .app.conga import Conga
from .const import (
    CONF_ANIMATE,
    CONF_EMAIL,
    CONF_PASSWORD,
    DOMAIN,
)

VERSION = "0.3.0"

_LOGGER = logging.getLogger(__name__)

PLATFORMS = (
    "vacuum",
    "camera",
)


CONFIG_SCHEMA = vol.Schema(
    {
        DOMAIN: vol.Schema(
            {
                vol.Optional(
                    CONF_EMAIL
                ): cv.string,

                vol.Optional(
                    CONF_PASSWORD
                ): cv.string,

                vol.Optional(
                    CONF_ANIMATE,
                    default=False,
                ): cv.boolean,
            }
        )
    },
    extra=vol.ALLOW_EXTRA,
)


def _normalize_identity(
    identity: Any,
) -> dict[str, Any] | None:
    """Validate and normalize a robot identity."""
    if not isinstance(identity, dict):
        return None

    serial = str(
        identity.get("serial") or ""
    ).strip()

    if (
        not serial
        or serial.lower()
        in {
            "0",
            "none",
            "null",
            "unknown",
        }
    ):
        return None

    alias = str(
        identity.get("alias") or ""
    ).strip()

    display_name = (
        alias
        or f"Conga {serial[-4:]}"
    )

    return {
        "serial": serial,
        "name": display_name,
        "alias": alias,
        "model": identity.get(
            "model"
        ),
        "firmware": identity.get(
            "firmware"
        ),
        "revision": identity.get(
            "revision"
        ),
    }


class IdentityPlatformLoader:
    """Load entity platforms after robot identity is available."""

    def __init__(
        self,
        hass,
        config,
        instance: Conga,
    ) -> None:
        """Initialize the loader."""
        self.hass = hass
        self.config = config
        self.instance = instance

        self._lock = asyncio.Lock()

        self._loaded_platforms: dict[
            str,
            set[str],
        ] = {}

        self._loading_serials: set[
            str
        ] = set()

        self._retry_tasks: dict[
            str,
            asyncio.Task,
        ] = {}

    def handle_identity_ready(
        self,
        identity,
    ) -> None:
        """Transfer the protocol-thread event to HA's loop."""
        normalized = _normalize_identity(
            identity
        )

        if normalized is None:
            _LOGGER.warning(
                "CongaMate ignored an invalid identity: %r",
                identity,
            )
            return

        _LOGGER.info(
            "CongaMate identity received: "
            "serial=%s name=%s",
            normalized["serial"],
            normalized["name"],
        )

        loop = self.hass.loop

        if loop.is_closed():
            return

        def enqueue() -> None:
            if self.hass.is_stopping:
                return

            self.hass.async_create_task(
                self.async_register(
                    normalized
                )
            )

        try:
            loop.call_soon_threadsafe(
                enqueue
            )
        except RuntimeError:
            return

    async def async_register(
        self,
        identity: dict[str, Any],
    ) -> None:
        """Load all missing platforms for one robot."""
        if self.hass.is_stopping:
            return

        serial = identity["serial"]

        self.hass.data[DOMAIN][
            "identities"
        ][serial] = dict(identity)

        async with self._lock:
            loaded = (
                self._loaded_platforms
                .setdefault(
                    serial,
                    set(),
                )
            )

            if loaded == set(PLATFORMS):
                return

            if serial in self._loading_serials:
                return

            self._loading_serials.add(
                serial
            )

        failed = False

        try:
            for platform in PLATFORMS:
                if self.hass.is_stopping:
                    return

                if platform in loaded:
                    continue

                try:
                    await discovery.async_load_platform(
                        self.hass,
                        platform,
                        DOMAIN,
                        dict(identity),
                        self.config,
                    )
                except Exception:
                    failed = True

                    _LOGGER.exception(
                        "Unable to load CongaMate "
                        "platform %s for serial %s",
                        platform,
                        serial,
                    )

                    continue

                loaded.add(platform)

                _LOGGER.info(
                    "Loaded CongaMate platform "
                    "%s for %s (%s)",
                    platform,
                    identity["name"],
                    serial,
                )

        finally:
            async with self._lock:
                self._loading_serials.discard(
                    serial
                )

        if (
            failed
            and not self.hass.is_stopping
            and loaded != set(PLATFORMS)
        ):
            self._schedule_retry(
                identity
            )

    def _schedule_retry(
        self,
        identity: dict[str, Any],
    ) -> None:
        """Retry missing platforms without duplication."""
        serial = identity["serial"]

        existing = self._retry_tasks.get(
            serial
        )

        if (
            existing is not None
            and not existing.done()
        ):
            return

        async def retry() -> None:
            try:
                await asyncio.sleep(15)

                if not self.hass.is_stopping:
                    await self.async_register(
                        identity
                    )
            finally:
                self._retry_tasks.pop(
                    serial,
                    None,
                )

        self._retry_tasks[serial] = (
            self.hass.async_create_task(
                retry()
            )
        )


async def async_setup(
    hass,
    config,
) -> bool:
    """Set up CongaMate from YAML."""
    if DOMAIN not in config:
        return True

    data = dict(
        config[DOMAIN]
    )

    email = (
        data.get(CONF_EMAIL)
        or os.environ.get(
            "CONGA_EMAIL"
        )
    )

    password = (
        data.get(CONF_PASSWORD)
        or os.environ.get(
            "CONGA_PASSWORD"
        )
    )

    if not email or not password:
        _LOGGER.error(
            "Missing CongaMate email or password"
        )
        return False

    instance = Conga(
        email,
        password,
        data[CONF_ANIMATE],
    )

    loader = IdentityPlatformLoader(
        hass,
        config,
        instance,
    )

    hass.data[DOMAIN] = {
        "config": data,
        "instance": instance,
        "identity_loader": loader,
        "identities": {},
    }

    # Critical ordering:
    # install the callback before starting the protocol client.
    instance.client.on(
        "identity_ready",
        loader.handle_identity_ready,
    )

    instance.start()

    return True
