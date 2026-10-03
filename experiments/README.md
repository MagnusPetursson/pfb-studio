# Generator experiments

Standalone algorithm studies live on `agent/generator-experiments`. They
export images and metadata through a Python CLI. The native PFB Studio application
still contains its five original generators; the optional C++ tool below runs
those originals for comparison. Nothing here is installed into the production app.

These are actual seeded algorithms, not image-generation prompts or stored presets.
See [the research brief](../docs/generator-research.md) for their provenance and
intended visual range.

The [first visual review](../docs/experiments/README.md) includes 24 default
seeds and eight additional seeds per study, twelve native references per original,
color/grayscale sheets, and the observed strengths and limitations of each direction.

## Minimal Perlin studies on black

The current audition refines `folded_veils`, `branched_light`, and
`inertial_filaments`. Each uses actual seeded Perlin gradient noise and carries
material color through the simulation. Finishing adds restrained local contrast,
fine Perlin modulation inside the forms, and small highlight bloom on black.
Each study has two transport controls and a shared `finish` control; `finish=0`
shows its current geometry with the original pale density rendering. These are
standalone prototypes.

Branched light and inertial filaments also have a `texture` control. Its default
adds sparse, compensated particle emission before rasterization; `texture=0`
replays the smooth colored finish from commit `030ce26`. Their transport and
camera are independent of this control. Folded veils retain their approved finish.

```powershell
./build/experiments/venv/Scripts/python.exe -m experiments.render --study perlin --seeds 1:24 --size 768 --jobs 3
./build/experiments/venv/Scripts/python.exe -m experiments.gallery --focus-perlin
./build/experiments/venv/Scripts/python.exe -m experiments.render --study perlin --seeds 1:4 --size 768 --control finish=0 --output build/experiments/unprocessed
```

The `perlin` group renders just these three. `all` includes all ten studies.
The focused gallery compares the refined studies with their previous colored
finishes under `build/experiments/gallery/smooth`, the saved first tests
under `build/experiments/gallery/baseline`, original Perlin/Fujii renders, and the
earlier attractor study. Omitting `--focus-perlin` restores the gallery of every
saved study. Both views use the existing gallery folder. The initial prototype
code and sheets are preserved at commit `5bc43b4`; `finish=0` disables finishing
on the current geometry, so it is not a substitute for that historical baseline.
New metadata hashes both shared Perlin and finishing sources as well as the study.
See the [particle texture review](../docs/experiments/perlin-texture/README.md),
[refinement review](../docs/experiments/perlin-refinement/README.md), and
[first-test review](../docs/experiments/perlin/README.md) for complete seed sheets.

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

## Run individual studies

```powershell
./build/experiments/venv/Scripts/python.exe -m experiments.render --list
./build/experiments/venv/Scripts/python.exe -m experiments.render --study all --seeds 1:24 --jobs 3
./build/experiments/venv/Scripts/python.exe -m experiments.render --study engravings --seeds 7 --control level_spacing=0.8
```

Names also include `engravings`, `membranes`, `attractors`, `geology`, `cells`,
`ecologies`, and `cities`. `--list` prints all named controls, normalized from 0 to 1.
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
