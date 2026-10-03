# Generator experiments

Seven standalone algorithm studies live on `agent/generator-experiments`. They
export images and metadata through a Python CLI. The native PFB Studio application
still contains its five original generators; the optional C++ tool below runs
those originals for comparison. Nothing here is installed into the production app.

These are actual seeded algorithms, not image-generation prompts or stored presets.
See [the research brief](../docs/generator-research.md) for their provenance and
intended visual range.

## Setup

Use Python 3.10 or later. From the repository root:

```powershell
python -m venv build/experiments/venv
./build/experiments/venv/Scripts/python.exe -m pip install -r experiments/requirements.txt
```

On Linux, the executable is `build/experiments/venv/bin/python`. The requirements
pin the principal numerical and drawing dependencies. Replay is checked within
one environment; identical pixels across library versions or platforms are not
promised.

## Run the seven studies

```powershell
./build/experiments/venv/Scripts/python.exe -m experiments.render --list
./build/experiments/venv/Scripts/python.exe -m experiments.render --study all --seeds 1:24 --jobs 3
./build/experiments/venv/Scripts/python.exe -m experiments.render --study engravings --seeds 7 --control level_spacing=0.8
```

Names are `engravings`, `membranes`, `attractors`, `geology`, `cells`, `ecologies`,
and `cities`. `--list` prints their named controls, all normalized from 0 to 1.
The default is 1024 × 1024; use `--width`, `--height`, or `--size` for dimensions
between 256 and 2048. Each PNG has a JSON companion recording the seed, controls,
algorithm details, runtime, pixel hash, and module source hash.

Outputs go to `build/experiments/gallery/experiments/<study>/`. A repeated command
replaces that exact study/seed output; use `--output` for a separate comparison.
Every seed is retained, including visually weak outputs.

## Native original reference sheets

Build in the normal C++ development environment:

```powershell
cmake -S . -B build/windows -G Ninja -DCMAKE_BUILD_TYPE=Release -DBUILD_TESTING=ON -DPFB_BUILD_EXPERIMENTS=ON
cmake --build build/windows --target pfb-reference-render
./build/experiments/venv/Scripts/python.exe -m experiments.reference_batch --executable build/windows/pfb-reference-render.exe --count 12 --jobs 3 --resume
```

The reference tool deliberately leaves the original automatic settings alone:
native resolution/aspect, default duration, warm-up, Fractal coefficient search,
and bloom. It never enables fixed-work benchmark mode. Time-limited originals
complete different amounts of work under different hardware and load; every
reference records actual elapsed time and work. Compare aesthetic form and
material, not performance or pixel equivalence. On Linux the reference process
requires a display, for example `xvfb-run -a` around the batch command.

## Review the results

```powershell
./build/experiments/venv/Scripts/python.exe -m experiments.gallery
./build/experiments/venv/Scripts/python.exe -m http.server 8766 --bind 127.0.0.1 --directory build/experiments/gallery
```

Open `http://127.0.0.1:8766`. The gallery includes every seed, full-resolution
image links, same-seed comparison selectors, and a grayscale toggle. Equal seed
numbers identify corresponding samples; unrelated algorithms interpret the
numbers independently. Color and grayscale contact sheets are also generated in
the `sheets` folder. The gallery works directly from `index.html` as well.

For the independent set:

```powershell
./build/experiments/venv/Scripts/python.exe -m experiments.render --study all --seeds 101:108 --output build/experiments/gallery/holdouts
```

Run regression tests with:

```powershell
./build/experiments/venv/Scripts/python.exe -m unittest discover -s experiments/tests -v
```

The control audition runner, `python -m experiments.audit --help`, renders low,
middle, and high settings and checks replay and framing. These mechanical checks
do not judge artistic quality. Aesthetic review must include the complete sheets,
weak examples, grayscale structure, and full-resolution detail.
