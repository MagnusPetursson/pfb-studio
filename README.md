# PFB Studio

PFB Studio is a native generative-art application with five renderers: noise
flowfield, fractal flame, organic growth, Fujii attractor, and galaxies.

This standalone repository was imported from
`MagnusPetursson/perlinfieldbot` commit `22bf197` as a fresh source snapshot.
The browser studio and historical standalone executables are intentionally not
part of this repository.

## Supported releases

- Windows 10/11 x64: one portable `PFBStudio.exe`.
- Linux Mint 22.x amd64: installable `.deb`.
- Linux x86_64: portable AppImage.

The v0.1 tester builds are unsigned. Windows may display a SmartScreen warning.

## Build on Linux

Install CMake 3.22+, Ninja, a C++17 compiler, and the X11/OpenGL development
packages required by SFML. Dependencies are downloaded at configure time and
pinned to immutable commits corresponding to the documented releases.

```sh
cmake --preset release-linux
cmake --build --preset release-linux
ctest --preset release-linux
```

Run the app:

```sh
./build/release-linux/pfb-studio
```

Create the Mint package:

```sh
cd build/release-linux
cpack -G DEB
```

## Verification commands

```sh
./build/release-linux/pfb-studio --version
xvfb-run -a ./build/release-linux/pfb-studio --smoke-test build/smoke
```

Smoke mode renders each generator with bounded settings and writes a report.
It is intended for release verification rather than normal batch rendering.

## Export behavior

`Save Image` writes the completed generator texture at its full output
resolution. PNG is the default; `.jpg` and `.jpeg` select JPEG encoding. Linux
uses Zenity when available and otherwise writes to the suggested Pictures path.
Windows uses the native save dialog.

## Current limits

- x64 only for the first tester release.
- No code signing, installer, automatic updates, presets, or saved settings.
- Replay reuses the seed, but wall-clock rendering does not guarantee
  pixel-identical output across machines.
- The legacy generator wrappers remain for v0.1 and will be replaced before the
  SFML 3 migration.

See [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md) for dependency attribution.
