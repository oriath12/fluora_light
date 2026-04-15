import asyncio
import datetime as dt
from enum import StrEnum
import socket

from homeassistant.components.light import (
    ATTR_BRIGHTNESS,
    ATTR_EFFECT,
    ATTR_HS_COLOR,
)
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import *


def scale_number(value, old_min, old_max, new_min, new_max):
    return ((value - old_min) / (old_max - old_min)) * (new_max - new_min) + new_min


def calculate_brightness_hex(desired_brightness):
    # clamp to [1, 100] so we never produce a value below the device's
    # documented minimum (HA brightness 1-2 would otherwise round to 0
    # and yield an out-of-range hex command).
    desired_brightness = max(1, min(100, desired_brightness))
    return scale_number((desired_brightness ** 0.1) - 1, 0, 100 ** 0.1 - 1, 3932160, 4160442)


class LightState(StrEnum):
    """dim of the light 0-100%"""
    BRIGHTNESS = ATTR_BRIGHTNESS
    """power true or false"""
    POWER = "power"
    """set the effect"""
    EFFECT = ATTR_EFFECT
    """(hue °, saturation %) tuple – HA convention"""
    HS_COLOR = ATTR_HS_COLOR


class LightCoordinator(DataUpdateCoordinator):
    _fast_poll_count = 0
    _normal_poll_interval = 60
    _fast_poll_interval = 10
    _initialized = False

    def __init__(self, hass, device_id, conf):
        # Keep the user-provided friendly name separate from the
        # DataUpdateCoordinator's `name` (which we prefix for logs).
        self.display_name = conf[CONF_NAME]
        self.device_id = device_id
        self.hostname = conf[CONF_HOSTNAME]
        self.port = conf[CONF_PORT]
        self._normal_poll_interval = 300
        self._fast_poll_interval = 5
        self._init_lock = asyncio.Lock()

        """Initialize coordinator parent"""
        super().__init__(
            hass,
            LOGGER,
            name="Fluora Light: " + self.display_name,
            # let's give at least 30 seconds for initial connect to device
            update_interval=dt.timedelta(seconds=30),
            update_method=self.async_update,
        )
        self.ip_address = "0.0.0.0"
        self.light_socket = None

        # Initialize state in case of new integration
        self.data = dict()
        # init to 255 since that's HA's representation of it
        self.data[LightState.BRIGHTNESS] = 255
        self.data[LightState.POWER] = True
        self.data[LightState.EFFECT] = EFFECT_AUTO
        # Default colour: red (0 °), fully saturated
        self.data[LightState.HS_COLOR] = (0.0, 100.0)

    def _set_poll_mode(self, fast: bool):
        self._fast_poll_count = 0 if fast else -1
        interval = self._fast_poll_interval if fast else self._normal_poll_interval
        self.update_interval = dt.timedelta(seconds=interval)
        self._schedule_refresh()

    def _update_poll(self):
        if self._fast_poll_count > -1:
            self._fast_poll_count += 1
            if self._fast_poll_count > 1:
                self._set_poll_mode(fast=False)

    def close(self):
        """Close the UDP socket. Called on unload."""
        if self.light_socket is not None:
            try:
                self.light_socket.close()
            except OSError:
                pass
            self.light_socket = None
        self._initialized = False

    async def async_update(self):
        if not self._initialized:
            await self._initialize()
        return self.data

    def _setup_socket(self):
        """Set up the UDP socket (runs in executor)."""
        self.ip_address = socket.gethostbyname(self.hostname)
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.settimeout(5)
        sock.connect((self.ip_address, self.port))
        self.light_socket = sock

    async def _send_hex(self, hex_str):
        """Send a hex command to the light without blocking the event loop."""
        if self.light_socket is None:
            LOGGER.debug("Skipping send: socket not initialized")
            return
        await self.hass.async_add_executor_job(
            self.light_socket.send, bytearray.fromhex(hex_str)
        )

    async def _initialize(self):
        # Guard against concurrent initialization (scheduled refresh +
        # user action can both call this).
        async with self._init_lock:
            if self._initialized:
                return
            try:
                # resolve hostname and set up socket in executor to avoid blocking
                await self.hass.async_add_executor_job(self._setup_socket)

                # set mode to auto when initializing
                await self._send_hex(AUTO_HEX)
                self.data[LightState.EFFECT] = EFFECT_AUTO
                self._initialized = True

                LOGGER.info(
                    "async_update_state: %s - %s", LightState.EFFECT, EFFECT_AUTO
                )

                self._set_poll_mode(fast=True)
            except Exception as e:
                # Make sure we don't leak a half-set-up socket on failure.
                if self.light_socket is not None:
                    try:
                        self.light_socket.close()
                    except OSError:
                        pass
                    self.light_socket = None
                LOGGER.warning(
                    "Failed to initialize %s: %s", self.hostname, str(e)
                )

    @property
    def state(self) -> dict:
        return self.data

    async def async_update_state(self, key: LightState, value) -> bool:
        return await self._async_update_state(key, value)

    async def _async_update_state(self, key: LightState, value) -> bool:
        if not self._initialized:
            await self._initialize()

        if not self._initialized:
            # initialization failed; nothing to send.
            return False

        # Write data back
        if key == LightState.BRIGHTNESS:
            # convert brightness from HA's 0-255 interpretation to our 0-100
            desired_brightness = round(value * 100 / 255)
            brightness_hex = calculate_brightness_hex(desired_brightness)
            await self._send_hex(BRIGHTNESS_HEX_FIRST + hex(int(brightness_hex))[2:] + BRIGHTNESS_HEX_LAST)
            LOGGER.info(f"Setting Brightness {desired_brightness}")
        # compiled all color, scene, and mode changing into the EFFECT to make it easier
        elif key == LightState.EFFECT:
            # check if it is a scene effect. If so, set the mode to scene and then set the specific scene
            if value in SCENE_EFFECTS:
                await self._send_hex(SCENE_HEX)
                await asyncio.sleep(0.1)
                await self._send_hex(SCENE_HEX_DICT[value])
                LOGGER.info(f"Setting SCENE: {value}")
            # check if it is 'auto' effect, and then change to auto mode
            elif value == EFFECT_AUTO:
                await self._send_hex(AUTO_HEX)
                LOGGER.info(f"Setting MODE: {value}")
            # if "White" is chosen, we need to set the saturation to 0, but don't need to change colors, also set to manual mode
            elif value == EFFECT_WHITE:
                await self._send_hex(MANUAL_HEX)
                await asyncio.sleep(0.1)
                await self._send_hex(MIN_SATURATION_HEX)
                LOGGER.info(f"Setting light to white")
            # finally check for color effects, where we need to set manual mode, set saturation to 100 and then set color
            elif value in COLOR_EFFECTS:
                await self._send_hex(MANUAL_HEX)
                await asyncio.sleep(0.1)
                await self._send_hex(MAX_SATURATION_HEX)
                await asyncio.sleep(0.1)
                await self._send_hex(SCENE_HEX_DICT[value])
                LOGGER.info(f"Setting color: {value}")
        elif key == LightState.HS_COLOR:
            hue, saturation = value
            await self._send_hex(MANUAL_HEX)
            await asyncio.sleep(0.1)
            await self._send_hex(build_hue_command(hue))
            await asyncio.sleep(0.1)
            await self._send_hex(build_saturation_command(saturation))
            # Clear any scene/mode effect so the UI reflects colour mode
            self.state[LightState.EFFECT] = None
            LOGGER.info("Setting HS colour: hue=%.1f°, saturation=%.1f%%", hue, saturation)
        elif key == LightState.POWER:
            if value:
                await self._send_hex(POWER_ON_HEX)
            else:
                await self._send_hex(POWER_OFF_HEX)
        else:
            return False

        self.state[key] = value

        LOGGER.info("async_update_state: %s - %s", key, value)

        self.async_set_updated_data(self.state)
        self._set_poll_mode(fast=True)

        return True
