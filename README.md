# Rocket League Boost Overlay

A local Streamlabs/OBS browser overlay for Rocket League boost. It reads Rocket League's local Stats API, bridges the raw TCP feed to a browser-friendly event stream, and lets you tune the boost meter in a browser editor.

## Features

- Live boost amount from Rocket League
- Streamlabs/OBS Browser Source support
- Browser editor for size, position, ring alignment, fill length, width, glow, color, and texture
- Built-in texture skins
- Custom texture folder for your own PNG boost meters
- Saved local config in `overlay-config.json`

## Requirements

- Windows
- Python 3
- Rocket League with the Stats API enabled
- Streamlabs Desktop or OBS

## Enable Rocket League Stats API

Close Rocket League first, then edit:

```txt
<Rocket League install>\TAGame\Config\DefaultStatsAPI.ini
```

For Steam, this is often:

```txt
D:\Steam\steamapps\common\rocketleague\TAGame\Config\DefaultStatsAPI.ini
```

Set:

```ini
[TAGame.MatchStatsExporter_TA]
Port=49123
PacketSendRate=10
```

Start Rocket League after saving.

## Run The Overlay Server

From this folder, run either:

```powershell
.\start-overlay.ps1
```

or:

```bat
start-overlay.bat
```

The server runs at:

```txt
http://127.0.0.1:8765
```

## Add To Streamlabs Or OBS

Add a Browser Source with:

```txt
http://127.0.0.1:8765/boost-overlay.html
```

Recommended source size:

```txt
1920 x 1080
```

## Edit The Meter

Open:

```txt
http://127.0.0.1:8765/boost-overlay.html?edit=1
```

Adjust the sliders, then click **Save**. Streamlabs/OBS uses the saved config automatically.

Useful controls:

- `X` / `Y`: position from the bottom-right corner
- `Size`: whole meter size
- `Center X` / `Center Y`: arc center
- `Radius`: arc circle size
- `Start`: where the arc begins
- `Length`: how far 100 boost fills
- `Total`: dash spacing; usually leave this alone unless tuning the arc behavior
- `Width`: visible fill thickness
- `Glow`: glow thickness
- `Color`: fill color
- `Image`: texture skin

## Add Custom Textures

Put PNG files in:

```txt
textures/custom
```

Then refresh the editor page:

```txt
http://127.0.0.1:8765/boost-overlay.html?edit=1
```

Your custom textures appear in the Image dropdown as `custom: filename`.

Texture tips:

- Use transparent PNGs.
- Square images work best.
- Built-in textures are `1266 x 1266`; matching that size makes alignment easier.

## Project Layout

```txt
boost-overlay.html          Browser overlay and editor
server.py                   Local Rocket League TCP bridge and static server
overlay-config.example.json Example saved config
textures/builtin            Included texture skins
textures/custom             User-added texture skins
start-overlay.ps1           PowerShell launcher
start-overlay.bat           Batch launcher
```

## Troubleshooting

If the overlay says disconnected:

- Make sure Rocket League is open.
- Make sure `PacketSendRate` is greater than `0`.
- Confirm Rocket League is listening on port `49123`.
- Restart `start-overlay.ps1` after changing server files.

If Streamlabs does not update:

- Right-click the Browser Source and refresh cache.
- Toggle the source off/on.
- Keep the URL as `http://127.0.0.1:8765/boost-overlay.html`.

If custom textures do not show:

- Confirm they are `.png` files.
- Put them directly inside `textures/custom`.
- Refresh the editor page.
