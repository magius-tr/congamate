""" CongaMate """
# pylint: disable=unused-argument
import logging
import os
import voluptuous as vol
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import discovery
from .app.conga import Conga
from .const import DOMAIN, CONF_EMAIL, CONF_PASSWORD, CONF_ANIMATE

VERSION = '0.0.0-development'

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_EMAIL): cv.string,
        vol.Optional(CONF_PASSWORD): cv.string,
        vol.Optional(CONF_ANIMATE, default=False): cv.boolean,
    })
}, extra=vol.ALLOW_EXTRA)

async def async_setup(hass, config):
    """ async_setup """
    if DOMAIN not in config:
        return True
    hass.data[DOMAIN] = {}
    hass.data[DOMAIN]['config'] = dict(config[DOMAIN])

    data = hass.data[DOMAIN]['config']

    email = data.get(CONF_EMAIL) or os.environ.get("CONGA_EMAIL")
    password = data.get(CONF_PASSWORD) or os.environ.get("CONGA_PASSWORD")

    if email and password:
        instance = Conga(email,
                         password,
                         data[CONF_ANIMATE])
        instance.start()
        hass.data[DOMAIN]['instance'] = instance
        await discovery.async_load_platform(
            hass, 'vacuum', DOMAIN, {}, config
        )
        await discovery.async_load_platform(
            hass, 'camera', DOMAIN, {}, config
        )
    else:
        logging.error('Missing configuration')

    return True
