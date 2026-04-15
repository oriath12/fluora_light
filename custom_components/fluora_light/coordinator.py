import asyncio
import datetime as dt
from enum import StrEnum
import json
import socket
import struct

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


def _parse_osc_packet(data: bytes) -> tuple[str, str, list]:
    """Minimal OSC 1.0 parser.  Returns (address, type_tag, args).

    Only handles types f (float32), i (int32), s (string), b (blob).
    Unknown types stop argument parsing early.
    """
    offset = 0

    # --- Address string (null-terminated, padded to 4-byte boundary) ---
    end = data.index(b"\x00", offset)
    address = data[offset:end].decode("ascii", errors="replace")
    offset = (end + 4) & ~3

    # --- Type-tag string (starts with ',') ---
    if offset >= len(data) or data[offset:offset + 1] != b",":
        return address, "", []
    end = data.index(b"\x00", offset)
    type_tag = data[offset:end].decode("ascii", errors="replace")
    offset = (end + 4) & ~3

    # --- Arguments ---
    args: list = []
    for t in type_tag[1:]:          # skip leading ','
        if t == "f":
            args.append(struct.unpack(">f", data[offset:offset + 4])[0])
            offset += 4
        elif t == "i":
            args.append(struct.unpack(">i", data[offset:offset + 4])[0])
            offset += 4
        elif t == "s":
            end = data.index(b"\x00", offset)
            args.append(data[offset:end].decode("utf-8", errors="replace"))
            offset = (end + 4) & ~3
        elif t == "b":
            size = struct.unpack(">i", data[offset:offset + 4])[0]
            offset += 4
            args.append(data[offset:offset + size])
            offset = (offset + size + 3) & ~3
        else:
            break  # unknown type, stop

    return address, type_tag, args


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

        # Background receive task and config-discovery state
        self._receive_task: asyncio.Task | None = None
        self._config_buffer: str = ""
        self.discovered_routes: dict[str, str] = {}

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
        """Cancel the receive loop and close the UDP socket. Called on unload."""
        if self._receive_task is not None and not self._receive_task.done():
            self._receive_task.cancel()
        self._receive_task = None

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

    # ------------------------------------------------------------------
    # Config-discovery: receive loop + OSC parsing
    # ------------------------------------------------------------------

    def _recv_blocking(self) -> bytes | None:
        """Blocking UDP recv — runs in executor.  Returns None on timeout/error."""
        try:
            return self.light_socket.recv(65535)
        except (socket.timeout, OSError):
            return None

    async def _receive_loop(self) -> None:
        """Background task: receive UDP packets from the device and parse them.

        All received OSC messages are logged at INFO level so that running
        ``grep fluora_light home-assistant.log`` after a Wireshark session
        gives the user a second source of truth for route discovery.
        """
        LOGGER.debug("Receive loop started for %s", self.hostname)
        while True:
            try:
                data = await self.hass.async_add_executor_job(self._recv_blocking)
                if data:
                    self._handle_received_packet(data)
            except asyncio.CancelledError:
                LOGGER.debug("Receive loop cancelled for %s", self.hostname)
                break
            except Exception as exc:
                LOGGER.debug("Receive loop error for %s: %s", self.hostname, exc)
                await asyncio.sleep(0.5)

    def _handle_received_packet(self, data: bytes) -> None:
        """Parse an incoming packet, log it, and collect config fragments."""
        try:
            address, type_tag, args = _parse_osc_packet(data)
        except Exception as exc:
            LOGGER.debug(
                "Unparseable packet from %s (%d bytes): %s  raw=%s",
                self.hostname, len(data), exc, data.hex(),
            )
            return

        LOGGER.info(
            "← OSC from %s  addr=%s  types=%s  args=%s",
            self.hostname, address, type_tag, args,
        )

        # Collect string args that look like JSON config fragments
        for arg in args:
            if isinstance(arg, str) and len(arg) > 10:
                self._accumulate_config(arg)

    def _accumulate_config(self, fragment: str) -> None:
        """Append a string fragment and try to parse the buffer as JSON."""
        self._config_buffer += fragment
        try:
            config = json.loads(self._config_buffer)
        except json.JSONDecodeError:
            return  # still incomplete

        LOGGER.info(
            "✓ Full device config received from %s:\n%s",
            self.hostname,
            json.dumps(config, indent=2),
        )
        self.discovered_routes = {}
        self._extract_routes(config, self.discovered_routes)
        LOGGER.info(
            "Discovered %d OSC routes from %s:",
            len(self.discovered_routes), self.hostname,
        )
        for label, route in self.discovered_routes.items():
            LOGGER.info("  %-30s → %s", label, route)

        self._config_buffer = ""  # reset for potential future updates

    def _extract_routes(self, obj: object, routes: dict, path: str = "") -> None:
        """Recursively walk the config tree and collect label→route pairs."""
        if isinstance(obj, dict):
            if "route" in obj and "label" in obj:
                routes[obj["label"]] = obj["route"]
            for key, val in obj.items():
                self._extract_routes(val, routes, f"{path}.{key}")
        elif isinstance(obj, list):
            for i, item in enumerate(obj):
                self._extract_routes(item, routes, f"{path}[{i}]")

    async def _probe_device_config(self) -> None:
        """Send no-argument OSC probes to try to elicit a config-tree response."""
        LOGGER.info("Probing %s for config tree (addresses: %s)…",
                    self.hostname, CONFIG_PROBE_ADDRESSES)
        for addr in CONFIG_PROBE_ADDRESSES:
            try:
                await self._send_hex(build_osc_probe(addr))
                await asyncio.sleep(0.3)
            except Exception as exc:
                LOGGER.debug("Probe %s failed: %s", addr, exc)

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

                # Start background receive loop so we capture any device responses
                self._receive_task = self.hass.async_create_task(
                    self._receive_loop()
                )

                # Probe for the config tree; response (if any) comes via receive loop
                await self._probe_device_config()

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
