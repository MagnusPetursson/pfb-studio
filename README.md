# PFB Studio

A native generative art application that explores procedural creation through multiple algorithmic approaches. PFB Studio lets you interactively generate and export unique artwork using six distinct mathematical renderers.

## Generators

- **Noise Flowfield** – Organic motion guided by Perlin noise patterns
- **Fractal Flame** – Iterated function systems creating intricate fractals
- **Organic Growth** – Simulated biological and natural growth patterns
- **Fujii Attractor** – Strange attractor-based visualizations
- **Galaxies** – Particle systems simulating stellar structures
- **Magnetic Loom** – Softened dipole fields traced into tapered, luminous filaments; an artistic field rather than a physically accurate magnetism simulation

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

On Windows, install Visual Studio 2022 Build Tools with the **Desktop development
with C++** workload, then run these commands in an x64 developer shell:

```powershell
cmake -S . -B build/windows -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON
cmake --build build/windows
ctest --test-dir build/windows --output-on-failure
./build/windows/PFBStudio.exe
```

SFML, Dear ImGui, and ImGui-SFML are pinned to specific revisions and fetched
at configure time. Platform development libraries are provided by the host
system.

## Usage

Launch the app, adjust parameters, and use **Save Image** to export artwork as PNG or JPEG at full resolution.

For automated testing on Linux (install `xvfb` for headless rendering):

```sh
ctest --preset release-linux
./build/release-linux/pfb-studio --version
xvfb-run -a ./build/release-linux/pfb-studio --smoke-test build/smoke
```

CTest includes support, palette, and rendering regression tests, plus a smoke
render of all six generators. On Linux it uses `xvfb-run` automatically when
available. Windows runs the same rendering checks directly.

Smoke mode completes a fixed amount of work for every generator, verifies that
rendering changes the image, and writes PNG outputs plus a JSON report. CTest
writes these to the build directory's `smoke` folder; the command above can be
used to choose another output folder.

The inspector's **Performance** panel reports setup time, render time, work
completed, and throughput. Enable **Fixed-work benchmark** or choose **Run
Benchmark** for comparisons with a pinned seed and identical parameters.
Benchmark mode ignores Duration (Magnetic Loom's **Time budget**); Fractal skips
its timed preprocess/bloom phases and Fujii starts drawing immediately. The
other five generators use the selected duration and visual phases in normal
mode.

To check that an optimization preserves artwork, compare the same seed,
parameters, and completed work. A faster time-limited render can produce a
different image because it completes more steps before its time budget ends.

### Magnetic Loom

Magnetic Loom traces a softened dipole field into tapered filaments. Adjust
**Symmetry** (2–10), **Turbulence**, **Twist**, **Spread**, **Hue**, and
**Exposure** to change the field and its rendering. Auto values are seeded, so
reusing a seed also reuses those choices.

An example with explicit controls:

| Control | Value |
| --- | --- |
| Seed | 424242 |
| Symmetry | 5 |
| Turbulence | 0.35 |
| Twist | 0.3 |
| Spread | 0.9 |
| Hue | 190 |
| Exposure | 1 |

Normal and benchmark modes use the same finite composition and work target.
In normal mode, **Time budget** is an upper limit: the composition may finish
early, while a shorter budget can stop it before completion. Benchmark mode
runs the composition to completion regardless of that budget. Compare completed
runs on the same build and graphics backend for fixed-work replay.

## Supported platforms

- **Windows 10+ (x64)** – Portable executable
- **Linux Mint 22+ (x64)** – Debian package
- **Linux x86_64** – AppImage

*v0.1 is x64 only. Builds are unsigned; Windows may display a SmartScreen warning.*

## Current limits

- There are no installers, automatic updates, saved presets, or persistent
  settings yet.
- Replaying a seed reuses generator inputs. Fixed-work comparisons require the
  same completed work; timed runs can finish at different points. Pixel-identical
  output across different machines or graphics backends is not guaranteed.

## License

See [LICENSE](LICENSE) and [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
