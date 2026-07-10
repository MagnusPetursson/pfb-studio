# PFB Studio

A native generative art application that explores procedural creation through multiple algorithmic approaches. PFB Studio lets you interactively generate and export unique artwork using five distinct mathematical renderers.

## Generators

- **Noise Flowfield** – Organic motion guided by Perlin noise patterns
- **Fractal Flame** – Iterated function systems creating intricate fractals
- **Organic Growth** – Simulated biological and natural growth patterns
- **Fujii Attractor** – Strange attractor-based visualizations
- **Galaxies** – Particle systems simulating stellar structures

## History

PFB Studio is a fork of [PerlinFieldBot](https://github.com/MagnusPetursson/perlinfieldbot), which was originally a Discord bot for generative art creation. This project replaces the bot interface with a native C++ desktop application, making the generators accessible as a standalone studio with reproducible builds for direct distribution.

## Getting started

### Linux/Windows (pre-built)

Download a release from the [releases page](../../releases).

The Windows x64 release is a portable executable and does not require an
installer or a separate runtime setup.

### Build from source

**Requirements:** CMake 3.22+, Ninja, and a C++17 compiler.

On Linux Mint or Ubuntu, install the system development packages first:

```sh
sudo apt install cmake ninja-build g++ libx11-dev libxrandr-dev \
    libxcursor-dev libxi-dev libudev-dev libfreetype-dev libgl1-mesa-dev
```

Then configure and build:

```sh
cmake --preset release-linux
cmake --build --preset release-linux
./build/release-linux/pfb-studio
```

SFML, Dear ImGui, and ImGui-SFML are pinned to specific revisions and fetched
at configure time. Platform development libraries are provided by the host
system.

## Usage

Launch the app, adjust parameters, and use **Save Image** to export artwork as PNG or JPEG at full resolution.

For automated testing:

```sh
ctest --preset release-linux
./build/release-linux/pfb-studio --version
xvfb-run -a ./build/release-linux/pfb-studio --smoke-test build/smoke
```

Smoke mode renders all five generators with bounded settings and writes PNG
outputs plus a JSON report. `xvfb-run` supplies the display required on a
headless Linux machine.

## Supported platforms

- **Windows 10+ (x64)** – Portable executable
- **Linux Mint 22+ (x64)** – Debian package
- **Linux x86_64** – AppImage

*v0.1 is x64 only. Builds are unsigned; Windows may display a SmartScreen warning.*

## Current limits

- There are no installers, automatic updates, saved presets, or persistent
  settings yet.
- Replaying a seed reuses generator inputs, but wall-clock rendering does not
  guarantee pixel-identical output across different machines.

## License

See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
