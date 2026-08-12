# PixelPipe Encoder — Portable package

1. Extract the entire `PixelPipe-Encoder-Portable-0.1.0.zip` archive.
2. Keep `PixelPipeEncoder.exe` and the `_internal` folder together.
3. Run `PixelPipeEncoder.exe`; no application installation is required.

PixelPipe settings and automatically downloaded FFmpeg tools are stored in the
current Windows user's Local AppData. This keeps the release ZIP small and
allows the same extracted app folder to be replaced during upgrades.

If FFmpeg is already installed and available through `PATH`, PixelPipe uses it
instead of downloading another copy.

The portable EXE is currently unsigned, so Windows SmartScreen may display an
`Unknown publisher` warning. Verify the ZIP's SHA-256 value against the release
`SHA256SUMS.txt` before running it.

