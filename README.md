# Fluora Light — Home Assistant Custom Integration

A Home Assistant custom integration for controlling [Fluora](https://fluoraplant.com/) LED lights over UDP on your local network. This gives you on/off, brightness, color, and scene control from the Home Assistant dashboard, automations, and voice assistants — without relying on the Fluora mobile app.

> **Compatibility:** This integration has been tested with the Fluora Mini. It may also work with the Fluora Floor Plant and Monos, as they share the same WiFi/UDP control protocol, but these are untested.

---

## Prerequisites

Before installing this integration, make sure you have:

- A **Fluora Mini** (or other Fluora device), fully assembled and powered on.
- The Fluora connected to your **2.4 GHz WiFi network** (the same network your Home Assistant instance is on).
- A running **Home Assistant** instance (2021.6 or later, which requires the `version` key in custom component manifests).
- **HACS** installed in Home Assistant (for the recommended install method).

---

## Step 1 — Assemble and Power On the Fluora Mini

If your Fluora Mini is already set up and glowing, skip to Step 2.

1. **Plug the stems into the pot.** Each stem connects to a labeled slot inside the ceramic pot.
2. **Attach the leaves to the stems.** Press each leaf connector firmly into the ports on each stem.
3. **Plug the power cable into a wall outlet.** The Fluora should light up in automatic mode (cycling through animations).

For detailed assembly instructions, refer to the [Fluora Mini setup guide](https://wiki.fluoraplant.com/setup/fluora-mini) or the printed manual that shipped with your device.

---

## Step 2 — Connect the Fluora to Your WiFi Network

The Fluora must be on your local WiFi network so Home Assistant can reach it over UDP.

1. Download the **Fluora mobile app** ([iOS](https://apps.apple.com/us/app/fluora/id1563305541) / [Android](https://play.google.com/store/apps/details?id=com.fluoramobileapp&hl=en_US)).
2. Put the Fluora into **pairing mode** by holding the function button (inside the pot) for **6 seconds** until the plant flashes blue.
3. In the app, tap the **+** icon, then **Discover Devices**.
4. Select your Fluora, tap **+**, and enter your **2.4 GHz WiFi network** name and password.
5. Press **Connect**. The plant should flash green three times to confirm a successful connection.

> **Important:** Fluora only supports **2.4 GHz** WiFi networks. If you have a dual-band router, make sure you're connecting to the 2.4 GHz band specifically.

If you run into issues, see the [Fluora WiFi troubleshooting page](https://wiki.fluoraplant.com/setup/wifi-setup).

---

## Step 3 — Find the Fluora's IP Address

This integration communicates with the Fluora over UDP, so you need its IP address (or a hostname that resolves to it) on your local network.

**Option A — Check your router's admin page.** Most routers list connected devices and their IP addresses. Look for a device named "Fluora" or similar.

**Option B — Use `arp -a` from a terminal.** On the same network, run:

```bash
arp -a
```

Look for the Fluora's MAC address or hostname in the list.

**Option C — Use a network scanner.** Apps like [Fing](https://www.fing.com/) (iOS/Android) or `nmap` can discover devices on your network.

> **Tip:** For reliability, assign a **static IP** or a **DHCP reservation** for your Fluora in your router settings. If the IP changes (e.g. after a DHCP lease renewal), the integration will lose contact until you update the config or restart.

---

## Step 4 — Install the Integration

### HACS (Recommended)

1. Open **HACS** in your Home Assistant instance.
2. Go to **Integrations** → **⋮** (top-right menu) → **Custom repositories**.
3. Add this repository URL: `https://github.com/dhoule36/fluora_light`
4. Set the category to **Integration** and click **Add**.
5. Search for **Fluora Light** in HACS and click **Download**.
6. **Restart Home Assistant.**

### Manual

1. Copy the `custom_components/fluora_light` folder from this repository into your Home Assistant `config/custom_components/` directory.
2. **Restart Home Assistant.**

---

## Step 5 — Add the Integration in Home Assistant

1. Go to **Settings** → **Devices & Services** → **Add Integration**.
2. Search for **Fluora Light**.
3. Enter the following:
   - **Name** — A friendly name for your light (e.g. "Living Room Fluora").
   - **Hostname** — The IP address or hostname of the Fluora on your network (from Step 3).
   - **Port** — The UDP port the Fluora listens on. The default is `6767`.
4. Click **Submit**. The light entity should appear under the new device.

Each config entry controls a single light. To add multiple Fluora devices, repeat this step for each one.

---

## Features

### Power

Standard on/off control from the Home Assistant UI, automations, scripts, or voice assistants.

### Brightness

Controlled via Home Assistant's brightness slider (0–255). The integration applies a perceptual curve so the slider feels more linear to the human eye.

### Effects

The following effects are available through Home Assistant's effect picker:

| Effect | Type | Description |
|--------|------|-------------|
| Auto | Mode | Automatic mode — cycles through animations |
| White | Color | Full white (minimum saturation) |
| Red | Color | Solid red at full saturation |
| Orange | Color | Solid orange at full saturation |
| Green | Color | Solid green at full saturation |
| Blue | Color | Solid blue at full saturation |
| Purple | Color | Solid purple at full saturation |
| Yellow | Color | Solid yellow at full saturation |
| Party | Scene | Animated scene preset |
| Chill | Scene | Animated scene preset |
| Focus | Scene | Animated scene preset |
| Bedtime | Scene | Animated scene preset |
| Awaken | Scene | Animated scene preset |

---

## Troubleshooting

### The light entity shows up but commands don't work

- Confirm the Fluora is powered on and connected to WiFi (it should be glowing, not dark).
- Verify the IP address is correct. Try pinging it: `ping <your-fluora-ip>`.
- Make sure UDP port `6767` (or your configured port) is not blocked by a firewall on your network.
- Make sure the Fluora and Home Assistant are on the **same subnet / VLAN**.

### The IP address changed and the integration stopped working

The Fluora's hostname is resolved once at initialization. If DHCP assigns a new IP, reload the integration or restart Home Assistant. Better yet, assign a static IP or DHCP reservation in your router.

### Home Assistant shows the wrong state

This integration is **fire-and-forget** — it sends UDP commands but does not read back the Fluora's actual state. If the light is changed via the Fluora app, the physical button, or another method, Home Assistant won't know. The state shown is always the last command HA sent. After a restart, HA assumes the light is **on at full brightness in Auto mode**.

### Commands are sometimes ignored

UDP does not guarantee delivery. On congested or unreliable WiFi, packets can be silently dropped. There is no retry or acknowledgment mechanism. If this happens frequently, try moving the Fluora closer to your router or switching to a wired backhaul for your HA instance.

---

## Known Limitations

- **No state feedback.** The integration cannot read the Fluora's current state. HA always displays the last commanded state.
- **UDP reliability.** Commands can be silently lost on unreliable networks. No retry logic.
- **Single device per config entry.** No bulk discovery or multi-device pairing. Add the integration once per Fluora.
- **No authentication.** UDP communication is unauthenticated. Any device on the same network can send commands to the Fluora.
- **Hardcoded protocol.** The hex command strings are hardcoded. A Fluora firmware update that changes the protocol would require updating this integration.
- **Brightness curve tuned for specific hardware.** The `x^0.1` perceptual curve was tuned for the Fluora Mini. Other Fluora models may respond differently.
- **5-second socket timeout.** If the Fluora is unreachable, the executor thread blocks for up to 5 seconds per command.

---

## Project Structure

```
custom_components/fluora_light/
├── __init__.py          # Entry setup / unload
├── config_flow.py       # UI-based configuration
├── const.py             # Constants, hex commands, effect lists
├── coordinator.py       # DataUpdateCoordinator — socket management & command sending
├── entity.py            # Base entity class
├── light.py             # LightEntity implementation
├── manifest.json        # HACS / HA metadata
├── strings.json         # Config flow UI strings
└── translations/
    └── en.json          # English translations
```

---

## Contributing

Contributions are welcome. If you'd like to add features (e.g. state polling, retry logic, support for additional Fluora models), please open an issue or pull request.

There are currently no automated tests. If you want to add them, `pytest-homeassistant-custom-component` can be used to mock the UDP socket and validate state transitions.

---

## License

See repository for license details.

---

## Disclaimer

This is an **unofficial**, community-built integration. It is not affiliated with, endorsed by, or supported by Fluora or color+light. Use at your own risk.
