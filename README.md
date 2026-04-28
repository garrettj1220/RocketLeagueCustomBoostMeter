# RL Custom UI

Custom Rocket League boost meter for OBS and Streamlabs, with two ways to use it:

- `Desktop app`: download the EXE, open it, customize the meter, copy the OBS browser source once, and leave the app running.
- `Open source`: run the local project from Python and change the HTML, textures, or behavior yourself.

## Download The EXE

If you just want the app:

**[Download the latest Windows EXE from GitHub Releases](https://github.com/garrettj1220/RocketLeagueCustomBoostMeter/releases/latest)**

You want:

```txt
RLCustomUI.exe
```

The desktop app and OBS both use the same local overlay URL:

```txt
http://127.0.0.1:8765/boost-overlay.html
```

`127.0.0.1` is correct for every user. The overlay is served from each person's own PC.

## What It Does

- Reads Rocket League's local Stats API on port `49123`
- Serves one stable browser source URL for OBS and Streamlabs
- Includes a desktop editor with a live embedded preview of the real overlay renderer
- Supports built-in skins and custom PNG skins
- Saves meter config locally between launches
- Supports launch with Windows and tray startup

## Quick Start

### Option 1: EXE download

For normal users:

1. Download the latest `RLCustomUI.exe` release from GitHub Releases.
2. Enable Rocket League Stats API using the config block below.
3. Open `RLCustomUI.exe`.
4. Copy the OBS URL from the app.
5. Add it as a Browser Source in OBS or Streamlabs.

### Option 2: Open source project

For users who want to run or modify the source:

```powershell
py -3 -m pip install -r requirements-desktop.txt
.\start-desktop-app.ps1
```

If you only want the local open-source bridge without the desktop app shell:

```powershell
.\start-overlay.ps1
```

## Enable Rocket League Stats API

Close Rocket League first, then edit:

```txt
<Rocket League install>\TAGame\Config\DefaultStatsAPI.ini
```

For Steam, this is often:

```txt
D:\Steam\steamapps\common\rocketleague\TAGame\Config\DefaultStatsAPI.ini
```

Use:

```ini
[TAGame.MatchStatsExporter_TA]
Port=49123
PacketSendRate=10
```

Restart Rocket League after saving.

Official Rocket League Stats API docs:

[Rocket League Stats API](https://www.rocketleague.com/en/developer/stats-api)

## OBS Setup

Add a Browser Source with:

```txt
http://127.0.0.1:8765/boost-overlay.html
```

Recommended source size:

```txt
1920 x 1080
```

The browser source stays the same. Users only set it up once.

## Customize

The desktop app is the main editor now.

Customize supports:

- skin selection with built-in style groups and custom uploads
- ring position and shape controls
- image size
- ring glow controls
- separate number and label positioning
- custom label text
- separate ring, number, label, and text glow colors
- separate number and label glow strength and blur

Changes save locally and update the live OBS source.

## Built-In And Custom Skins

Built-in skins live in:

```txt
textures/builtin/style-1
textures/builtin/style-2
```

User PNG skins are stored in:

```txt
%LOCALAPPDATA%\RLCustomUI\textures\custom
```

Example on Windows:

```txt
C:\Users\<YourUser>\AppData\Local\RLCustomUI\textures\custom
```

The desktop app also supports `Add custom skin` directly from the file picker.

## Project Layout

```txt
boost-overlay.html          Actual browser source used by OBS and the app preview
desktop-ui.html             WebView desktop app UI
webview_app.py              Main desktop app entrypoint
boost_meter_core.py         Shared bridge, config, texture, and local server logic
server.py                   Minimal open-source local bridge entrypoint
requirements-desktop.txt    Python dependencies for the desktop app
start-desktop-app.ps1       Run the desktop app from source
start-desktop-app.bat       Windows batch launcher for the desktop app
start-overlay.ps1           Run the open-source bridge from source
start-overlay.bat           Windows batch launcher for the bridge
textures/builtin/style-1    Built-in skin set 1
textures/builtin/style-2    Built-in skin set 2
textures/custom             Placeholder folder for user skins in source mode
overlay-config.example.json Example config
```

## Build The EXE

To package the app yourself:

```powershell
py -3 -m pip install -r requirements-desktop.txt
py -3 -m PyInstaller --noconfirm --clean --windowed --name RLCustomUI --icon "app-icon.ico" --add-data "boost-overlay.html;." --add-data "desktop-ui.html;." --add-data "app-icon.png;." --add-data "app-icon.ico;." --add-data "textures;textures" --hidden-import webview.platforms.winforms --hidden-import pythonnet --hidden-import clr_loader "webview_app.py"
```

Output:

```txt
dist\RLCustomUI\RLCustomUI.exe
```

## Troubleshooting

If the overlay does not update:

- Make sure Rocket League is open.
- Make sure `PacketSendRate` is greater than `0`.
- Restart Rocket League after changing `DefaultStatsAPI.ini`.
- Keep the Browser Source URL as `http://127.0.0.1:8765/boost-overlay.html`.

If the desktop app opens but the preview is blank:

- Make sure Microsoft Edge WebView2 Runtime is installed.

If the app icon looks wrong after replacing builds:

- Delete old shortcuts and pin the new EXE again.

If custom skins do not show:

- Use transparent `.png` files.
- Keep them square when possible.
- Reload the app after adding a large batch of skins.
