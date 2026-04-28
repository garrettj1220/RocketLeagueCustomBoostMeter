# Release Title

`RLCustomUI v1.0.0`

# Release Body

## Download

For most users, download:

```txt
RLCustomUI.exe
```

## What This Is

RL Custom UI is a Rocket League boost meter for OBS and Streamlabs.

- simple EXE workflow for normal users
- open-source source build for modders
- real embedded preview that matches the actual browser source
- built-in skins and custom PNG skins

## Setup

1. Enable Rocket League Stats API in `DefaultStatsAPI.ini`
2. Open `RLCustomUI.exe`
3. Copy the OBS URL from the app
4. Add it as a Browser Source in OBS or Streamlabs

OBS URL:

```txt
http://127.0.0.1:8765/boost-overlay.html
```

## Notes

- `127.0.0.1` is correct for every user because the overlay runs locally on their own PC.
- The app must be running while the OBS browser source is in use.
- WebView2 Runtime may be required on Windows if it is not already installed.
