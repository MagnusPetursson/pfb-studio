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

### macOS/Linux/Windows (pre-built)

Download a release from the [releases page](../../releases).

### Build from source

**Requirements:** CMake 3.22+, Ninja, C++17 compiler

**Linux:** X11 and OpenGL development packages (handled automatically)

```sh
cmake --preset release-linux
cmake --build --preset release-linux
./build/release-linux/pfb-studio
```

All dependencies are pinned to specific versions and fetched at build time.

## Usage

Launch the app, adjust parameters, and use **Save Image** to export artwork as PNG or JPEG at full resolution.

For automated testing:
```sh
./build/release-linux/pfb-studio --version
./build/release-linux/pfb-studio --smoke-test build/smoke
```

## Supported platforms

- **Windows 10+ (x64)** – Portable executable
- **Linux Mint 22+ (x64)** – Debian package
- **Linux x86_64** – AppImage

*v0.1 is x64 only. Builds are unsigned; Windows may display a SmartScreen warning.*

## License

See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
