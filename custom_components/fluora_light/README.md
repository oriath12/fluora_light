# Fluora Light - Home Assistant Custom Integration

A Home Assistant custom integration for controlling Fluora LED lights over UDP on your local network.

## Installation

### HACS (Recommended)

1. Open HACS in your Home Assistant instance.
2. Go to **Integrations** > **Custom repositories**.
3. Add this repository URL and select **Integration** as the category.
4. Search for "Fluora Light" and install it.
5. Restart Home Assistant.

### Manual

1. Copy the `custom_components/fluora_light` folder into your Home Assistant `config/custom_components/` directory.
2. Restart Home Assistant.

## Setup

1. In Home Assistant, go to **Settings** > **Devices & Services** > **Add Integration**.
2. Search for **Fluora Light**.
3. Enter the following:
   - **Name**: A friendly name for your light (e.g. "Desk Lamp").
   - **Hostname**: The hostname or IP address of the light on your local network. You can find this by running `arp -a` on your machine.
   - **Port**: The UDP port the light listens on (default: `6767`).

Each config entry controls a single light. To add multiple lights, add the integration once per device.

## Features

### Brightness

Brightness is controlled via Home Assistant's standard brightness slider (0-255). The integration applies a perceptual curve (`x^0.1`) so that the slider feels more linear to the human eye.

### Effects

The integration exposes the following effects through Home Assistant's effect picker:

| Effect | Type | Description |
|--------|------|-------------|
| Auto | Mode | Sets the light to automatic mode |
| White | Color | Full white (minimum saturation) |
| Red, Orange, Green, Blue, Purple, Yellow | Color | Solid color at full saturation |
| Party, Chill, Focus, Bedtime, Awaken | Scene | Built-in animated scene presets |

### Power

Standard on/off control via the Home Assistant UI, automations, or voice assistants.

## Testing

### Prerequisites

- A Fluora light on the same local network as your Home Assistant instance.
- The light must be reachable by hostname or IP from the HA host.
- UDP port 6767 (or your configured port) must not be blocked by a firewall.

### Manual Testing Checklist

1. **Discovery & Setup**
   - Add the integration via the UI. Confirm the config flow completes without errors.
   - Verify the light entity appears under the device.

2. **Power**
   - Toggle the light on and off from the HA dashboard.

3. **Brightness**
   - Move the brightness slider. Confirm the physical light responds.
   - Test extremes: set brightness to 1 (dimmest) and 255 (brightest).

4. **Effects**
   - Select each effect from the effect dropdown and confirm the light changes accordingly.
   - Cycle through color effects (Red, Green, Blue, etc.), scene effects (Party, Chill, etc.), Auto, and White.

5. **Reconnection**
   - Power cycle the light hardware. After it comes back, trigger a command and confirm it still works (the coordinator re-initializes on the next poll or command).

6. **Multiple Lights**
   - Add two or more lights. Confirm they can be independently controlled without cross-talk.

### Automated / Unit Testing

There are currently no automated tests. If you want to add them, you can use `pytest-homeassistant-custom-component` to mock the UDP socket and validate state transitions.

## Known Blindspots & Assumptions

### No State Feedback

The integration is **fire-and-forget**. It sends UDP commands to the light but does **not** read back the light's actual state. This means:

- If someone changes the light via another method (physical button, other app), Home Assistant will not reflect that change.
- The state shown in HA is always the *last commanded* state, not the *actual* state.
- After a Home Assistant restart, the integration assumes the light is **on at full brightness in Auto mode**, which may not match reality.

### UDP Reliability

UDP does not guarantee delivery. Commands can be silently lost, especially on congested or unreliable Wi-Fi networks. There is no retry or acknowledgment mechanism — if a packet is dropped, the light simply won't respond and HA won't know.

### Hostname Resolution

- `socket.gethostbyname()` is used to resolve the configured hostname. If DNS or mDNS is unreliable on your network, use a static IP address instead.
- The hostname is resolved once at initialization. If the light's IP changes (e.g. DHCP lease renewal), you will need to reload the integration or restart HA.

### Brightness Curve

The brightness conversion uses a `x^0.1` perceptual curve mapped to a fixed hex range (`3932160` to `4160442`). This was tuned for specific Fluora hardware. If your light model differs, the perceived brightness response may not feel linear.

### Blocking Considerations

Socket setup and hex sends are wrapped in `async_add_executor_job` to avoid blocking the Home Assistant event loop. However, the socket has a 5-second timeout — if the light is unreachable, the executor thread will block for up to 5 seconds per command.

### Single Device Per Entry

Each config entry controls exactly one light. There is no bulk discovery or multi-device support.

### No Authentication

Communication with the light is unauthenticated UDP. Any device on the same network can send commands to the light.

### Hardcoded Protocol

The hex command strings are hardcoded in `const.py`. If Fluora releases a firmware update that changes the protocol, the integration will need to be manually updated.

## Project Structure

\```
custom_components/fluora_light/
├── __init__.py        # Entry setup/unload
├── config_flow.py     # UI-based configuration
├── const.py           # All constants, hex commands, effect lists
├── coordinator.py     # DataUpdateCoordinator — socket management & command sending
├── entity.py          # Base entity class
├── light.py           # LightEntity implementation
├── manifest.json      # HACS/HA metadata
├── strings.json       # Config flow UI strings
└── translations/
    └── en.json        # English translations
\```

## License

See repository for license details.
