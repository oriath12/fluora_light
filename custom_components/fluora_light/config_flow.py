"""Config flow for Fluora Light."""

from __future__ import annotations

import socket
from typing import TYPE_CHECKING, Any

import voluptuous as vol

from homeassistant import config_entries
from homeassistant.data_entry_flow import FlowResult

from .const import (
    AUTO_HEX,
    CONF_HOSTNAME,
    CONF_NAME,
    CONF_PORT,
    DEFAULT_NAME,
    DEFAULT_PORT,
    DOMAIN,
    LOGGER,
)

if TYPE_CHECKING:
    # Imported only for type hints to avoid pulling in optional HA components
    # (dhcp/zeroconf) at module load time.
    from homeassistant.components import dhcp, zeroconf


def _probe_device(hostname: str, port: int) -> str:
    """Resolve *hostname* and send a single UDP packet to *port*.

    Runs in an executor. Returns the resolved IP on success. Raises
    :class:`OSError` (including ``socket.gaierror``) if the hostname can't
    be resolved or the OS refuses to open/send on the socket.

    Note: because the Fluora protocol is fire-and-forget UDP, a successful
    send does NOT prove there's actually a Fluora at the address — only
    that we can reach the network and the hostname resolves. That's the
    best we can verify from Home Assistant without a device response.
    """
    ip = socket.gethostbyname(hostname)
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        sock.settimeout(2)
        sock.connect((ip, port))
        sock.send(bytearray.fromhex(AUTO_HEX))
    finally:
        sock.close()
    return ip


class FluoraFlowHandler(config_entries.ConfigFlow, domain=DOMAIN):
    """Handle a config flow for Fluora Light."""

    VERSION = 1

    def __init__(self) -> None:
        self._host: str | None = None
        self._name: str | None = None
        self._port: int = DEFAULT_PORT

    # ---------------- manual entry ----------------

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Handle a flow initialized by the user."""
        errors: dict[str, str] = {}

        if user_input is not None:
            host = user_input[CONF_HOSTNAME]
            port = user_input[CONF_PORT]
            name = user_input[CONF_NAME]

            await self.async_set_unique_id(host, raise_on_progress=False)
            self._abort_if_unique_id_configured()

            try:
                await self.hass.async_add_executor_job(_probe_device, host, port)
            except OSError as err:
                LOGGER.warning("Fluora probe failed for %s: %s", host, err)
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(title=name, data=user_input)

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self._name or DEFAULT_NAME
                    ): str,
                    vol.Required(
                        CONF_HOSTNAME, default=self._host or ""
                    ): str,
                    vol.Optional(CONF_PORT, default=self._port): vol.Coerce(int),
                }
            ),
            errors=errors,
        )

    # ---------------- zeroconf discovery ----------------

    async def async_step_zeroconf(
        self, discovery_info: "zeroconf.ZeroconfServiceInfo"
    ) -> FlowResult:
        """Handle a flow initialized by zeroconf / mDNS discovery."""
        host = discovery_info.host
        port = discovery_info.port or DEFAULT_PORT
        # Strip the service-type suffix from the instance name, e.g.
        # "Fluora-ABC123._osc._udp.local." -> "Fluora-ABC123".
        raw_name = discovery_info.name or ""
        name = raw_name.split(".", 1)[0] or DEFAULT_NAME

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured(
            updates={CONF_HOSTNAME: host, CONF_PORT: port}
        )

        self._host = host
        self._port = port
        self._name = name

        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_discovery_confirm()

    # ---------------- dhcp discovery ----------------

    async def async_step_dhcp(
        self, discovery_info: "dhcp.DhcpServiceInfo"
    ) -> FlowResult:
        """Handle a flow initialized by DHCP discovery."""
        host = discovery_info.ip
        name = discovery_info.hostname or DEFAULT_NAME

        await self.async_set_unique_id(host)
        self._abort_if_unique_id_configured(updates={CONF_HOSTNAME: host})

        self._host = host
        self._port = DEFAULT_PORT
        self._name = name

        self.context["title_placeholders"] = {"name": name}
        return await self.async_step_discovery_confirm()

    # ---------------- confirm step shared by discovery flows ----------------

    async def async_step_discovery_confirm(
        self, user_input: dict[str, Any] | None = None
    ) -> FlowResult:
        """Prompt the user to confirm a discovered Fluora."""
        assert self._host is not None
        errors: dict[str, str] = {}

        if user_input is not None:
            name = user_input.get(CONF_NAME, self._name or DEFAULT_NAME)
            try:
                await self.hass.async_add_executor_job(
                    _probe_device, self._host, self._port
                )
            except OSError as err:
                LOGGER.warning(
                    "Fluora probe failed for discovered %s: %s", self._host, err
                )
                errors["base"] = "cannot_connect"
            else:
                return self.async_create_entry(
                    title=name,
                    data={
                        CONF_NAME: name,
                        CONF_HOSTNAME: self._host,
                        CONF_PORT: self._port,
                    },
                )

        return self.async_show_form(
            step_id="discovery_confirm",
            data_schema=vol.Schema(
                {
                    vol.Required(
                        CONF_NAME, default=self._name or DEFAULT_NAME
                    ): str,
                }
            ),
            description_placeholders={
                "name": self._name or DEFAULT_NAME,
                "host": self._host,
            },
            errors=errors,
        )
