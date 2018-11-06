"""
Support for KNX/IP lights.

For more details about this platform, please refer to the documentation at
https://home-assistant.io/components/light.knx/
"""

import voluptuous as vol

from homeassistant.components.knx import ATTR_DISCOVER_DEVICES, DATA_KNX
from homeassistant.components.light import (
    ATTR_BRIGHTNESS, ATTR_HS_COLOR, PLATFORM_SCHEMA, SUPPORT_BRIGHTNESS,
    SUPPORT_COLOR, Light)
from homeassistant.const import CONF_NAME
from homeassistant.core import callback
import homeassistant.helpers.config_validation as cv
import homeassistant.util.color as color_util

CONF_ADDRESS = 'address'
CONF_STATE_ADDRESS = 'state_address'
CONF_BRIGHTNESS_ADDRESS = 'brightness_address'
CONF_BRIGHTNESS_STATE_ADDRESS = 'brightness_state_address'
CONF_COLOR_ADDRESS = 'color_address'
CONF_COLOR_STATE_ADDRESS = 'color_state_address'

DEFAULT_NAME = 'KNX Light'
DEFAULT_COLOR = [255, 255, 255]
DEFAULT_BRIGHTNESS = 255
DEPENDENCIES = ['knx']

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_ADDRESS): cv.string,
    vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
    vol.Optional(CONF_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_BRIGHTNESS_ADDRESS): cv.string,
    vol.Optional(CONF_BRIGHTNESS_STATE_ADDRESS): cv.string,
    vol.Optional(CONF_COLOR_ADDRESS): cv.string,
    vol.Optional(CONF_COLOR_STATE_ADDRESS): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Set up lights for KNX platform."""
    if discovery_info is not None:
        async_add_entities_discovery(hass, discovery_info, async_add_entities)
    else:
        async_add_entities_config(hass, config, async_add_entities)


@callback
def async_add_entities_discovery(hass, discovery_info, async_add_entities):
    """Set up lights for KNX platform configured via xknx.yaml."""
    entities = []
    for device_name in discovery_info[ATTR_DISCOVER_DEVICES]:
        device = hass.data[DATA_KNX].xknx.devices[device_name]
        entities.append(KNXLight(hass, device))
    async_add_entities(entities)


@callback
def async_add_entities_config(hass, config, async_add_entities):
    """Set up light for KNX platform configured within platform."""
    import xknx
    light = xknx.devices.Light(
        hass.data[DATA_KNX].xknx,
        name=config.get(CONF_NAME),
        group_address_switch=config.get(CONF_ADDRESS),
        group_address_switch_state=config.get(CONF_STATE_ADDRESS),
        group_address_brightness=config.get(CONF_BRIGHTNESS_ADDRESS),
        group_address_brightness_state=config.get(
            CONF_BRIGHTNESS_STATE_ADDRESS),
        group_address_color=config.get(CONF_COLOR_ADDRESS),
        group_address_color_state=config.get(CONF_COLOR_STATE_ADDRESS))
    hass.data[DATA_KNX].xknx.devices.add(light)
    async_add_entities([KNXLight(hass, light)])


class KNXLight(Light):
    """Representation of a KNX light."""

    def __init__(self, hass, device):
        """Initialize of KNX light."""
        self.device = device
        self.hass = hass
        self.async_register_callbacks()

    @callback
    def async_register_callbacks(self):
        """Register callbacks to update hass after device was changed."""
        async def after_update_callback(device):
            """Call after device was updated."""
            await self.async_update_ha_state()
        self.device.register_device_updated_cb(after_update_callback)

    @property
    def name(self):
        """Return the name of the KNX device."""
        return self.device.name

    @property
    def available(self):
        """Return True if entity is available."""
        return self.hass.data[DATA_KNX].connected

    @property
    def should_poll(self):
        """No polling needed within KNX."""
        return False

    @property
    def brightness(self):
        """Return the brightness of this light between 0..255."""
        if self.device.supports_color:
            if self.device.current_color is None:
                return None
            return max(self.device.current_color)
        if self.device.supports_brightness:
            return self.device.current_brightness
        return None

    @property
    def hs_color(self):
        """Return the HS color value."""
        if self.device.supports_color:
            rgb = self.device.current_color
            if rgb is None:
                return None
            return color_util.color_RGB_to_hs(*rgb)
        return None

    @property
    def color_temp(self):
        """Return the CT color temperature."""
        return None

    @property
    def white_value(self):
        """Return the white value of this light between 0..255."""
        return None

    @property
    def effect_list(self):
        """Return the list of supported effects."""
        return None

    @property
    def effect(self):
        """Return the current effect."""
        return None

    @property
    def is_on(self):
        """Return true if light is on."""
        return self.device.state

    @property
    def supported_features(self):
        """Flag supported features."""
        flags = 0
        if self.device.supports_brightness:
            flags |= SUPPORT_BRIGHTNESS
        if self.device.supports_color:
            flags |= SUPPORT_COLOR | SUPPORT_BRIGHTNESS
        return flags

    async def async_turn_on(self, **kwargs):
        """Turn the light on."""

        # initialize with current values
        brightness = self.brightness
        hs_color = self.hs_color

        # overwrite values with new settings, if available
        if ATTR_BRIGHTNESS in kwargs:
            brightness = int(kwargs[ATTR_BRIGHTNESS])
        if ATTR_HS_COLOR in kwargs:
            hs_color = kwargs[ATTR_HS_COLOR]

        # fall back to default values, if required
        if brightness is None:
            brightness = DEFAULT_BRIGHTNESS
        if hs_color is None:
            hs_color = DEFAULT_COLOR

        update_brightness = ATTR_BRIGHTNESS in kwargs
        update_color = ATTR_HS_COLOR in kwargs

        # always only go one path for turning on (avoid conflicting changes
        # and weird effects)
        if self.device.supports_brightness and \
                (update_brightness and not update_color):
            # if we don't need to update the color, try updating brightness
            # directly if supported; don't do it if color also has to be changed,
            # as RGB color implicitly sets the brightness as well
            await self.device.set_brightness(brightness)
        elif self.device.supports_color and \
                (update_brightness or update_color):
            # change RGB color (includes brightness)
            await self.device.set_color(
                color_util.color_hsv_to_RGB(*hs_color, brightness * 100 / 255))
        else:
            # no color/brightness change requested, so just turn it on
            await self.device.set_on()

    async def async_turn_off(self, **kwargs):
        """Turn the light off."""
        await self.device.set_off()
