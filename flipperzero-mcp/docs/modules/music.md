# `music` module

The `music` module saves and optionally plays songs on the Flipper Zero using the Music Player app and Flipper Music Format (FMF).

## Storage location

- Songs are stored under `/ext/apps_data/music_player` on the SD card
- This module requires a MicroSD card

## Tools

### `music_get_format`

Returns the FMF (Flipper Music Format) specification that the module expects.

### `music_play`

Validates FMF song data, writes a `.fmf` file to the device, and optionally launches the Music Player app to play it.

Parameters:

- `song_data` (string; required): FMF content
- `filename` (string; optional): filename to save (the module will sanitize it and ensure `.fmf`)
- `play_immediately` (boolean; default: `true`)

Notes:

- Validation is implemented in `flipper_mcp.modules.music.formatter.validate_fmf_format`.
- App launching is not implemented over protobuf RPC in this repo yet; the tool saves the file and instructs you to open Music Player manually.


