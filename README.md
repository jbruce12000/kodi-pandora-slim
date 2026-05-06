# Pandora Player for Kodi

A Kodi plugin that enables streaming Pandora music stations directly within Kodi.

## Features

- Browse and play Pandora stations
- High-quality audio streaming
- Integrated with Kodi's music playback system
- Username/password authentication via settings
- No dependencies

## Requirements

- Kodi
- Python 3.x (included with Kodi)

## Installation

1. Download `plugin.audio.pandora.zip`
2. In Kodi, go to **Add-ons** > **Install from zip file**
3. Select the downloaded ZIP file
4. The plugin will appear in your add-ons list

## Configuration

1. Navigate to **Add-ons** > **My add-ons** > **Music add-ons** > **Pandora Player**
2. Select **Configure**
3. Enter your Pandora username and password

## Usage

1. Go to **Music** > **Music add-ons** > **Pandora Player**
2. Select a station to start playing
3. Use Kodi's built-in controls for playback

## Building from Source

Run the build script to create a distributable ZIP:

```bash
python3 build_plugin.py
```

This generates `plugin.audio.pandora.zip` with auto-generated version info.

## Project Structure

```
pandora/
├── plugin.audio.pandora/          # Source directory
│   ├── addon.xml                # Add-on manifest
│   ├── default.py              # Main plugin entry
│   ├── service.py               # Background service
│   └── resources/
│       ├── lib/
│       │   ├── pandora_api.py  # Pandora API client
│       │   ├── blowfish.py    # Blowfish cipher (GPL)
│       │   └── version.py    # Build version
│       └── settings.xml         # Settings definition
├── build_plugin.py             # Build script
└── README.md
```

## Technical Notes

- Uses Pandora's web API with Blowfish ECB encryption
- Authenticates via partner login flow
- Supports station listing and playlist retrieval
- Compatible with Kodi Python 3.0.0 API

## License

- **blowfish.py**: GNU General Public License v3
- **All other code**: See LICENSE file

## Version

Current version: **3.0.0** (Build: starlight-final)
