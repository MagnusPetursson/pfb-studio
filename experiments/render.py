"""Render reproducible, isolated algorithm studies and their metadata.

Run from the repository root: python -m experiments.render --study all --seeds 1:24
"""
import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
import hashlib
import importlib
import json
import math
import os
from pathlib import Path
import time

# Keep batch workers from each spawning an entire BLAS thread pool.
for _name in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_name, "1")
os.environ.setdefault("MPLBACKEND", "Agg")

PERLIN_STUDIES = ("folded_veils", "branched_light", "inertial_filaments")
STUDIES = ("engravings", "membranes", "attractors", "geology", "cells", "ecologies", "cities", *PERLIN_STUDIES)


def seed_list(value):
    try:
        if ":" in value:
            start, end = map(int, value.split(":"))
            seeds = list(range(start, end + 1)) if 0 <= end - start < 1000 else []
        else:
            seeds = [int(v) for v in value.split(",")]
        if not seeds or len(seeds) > 1000 or len(set(seeds)) != len(seeds) or any(s < 1 or s >= 2**64 for s in seeds):
            raise ValueError()
        return seeds
    except ValueError:
        raise argparse.ArgumentTypeError("Use positive seeds, e.g. 1:24 or 1,4,9 (at most 1000)")


def controls_for(module, provided):
    declared = module.CONTROLS
    unknown = set(provided) - set(declared)
    if unknown:
        raise ValueError(f"Unknown controls for {module.__name__}: {', '.join(sorted(unknown))}")
    values = {name: float(spec["default"]) for name, spec in declared.items()}
    values.update(provided)
    if any(not math.isfinite(v) or not 0 <= v <= 1 for v in values.values()):
        raise ValueError("Control values must be finite and in [0,1]")
    return values


def render_one(name, seed, width, height, controls, root):
    from PIL import Image
    module = importlib.import_module(f"experiments.studies.{name}")
    values = controls_for(module, controls)
    started = time.perf_counter()
    image, details = module.render(seed, width, height, values)
    elapsed = time.perf_counter() - started
    if not isinstance(image, Image.Image) or image.size != (width, height):
        raise ValueError(f"{name} returned an invalid image or size")
    image = image.convert("RGB")
    output = Path(root) / name / f"seed-{seed:04d}.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    image.save(output)
    data = {"kind": "experiment", "generator": name, "title": module.TITLE,
            "seed": seed, "width": width, "height": height, "controls": values,
            "render_seconds": elapsed,
            "pixel_sha256": hashlib.sha256(image.tobytes()).hexdigest(),
            "source_sha256": hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest(),
            "details": details}
    if name in PERLIN_STUDIES:
        shared = Path(module.__file__).with_name("perlin_common.py")
        data["source_dependencies_sha256"] = {shared.name: hashlib.sha256(shared.read_bytes()).hexdigest()}
    output.with_suffix(".json").write_text(json.dumps(data, indent=2, allow_nan=False), encoding="utf-8")
    return f"{name} seed={seed} {width}x{height} {elapsed:.2f}s -> {output}"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", choices=("all", "perlin", *STUDIES), default="all")
    parser.add_argument("--seeds", type=seed_list, default=seed_list("1:24"))
    parser.add_argument("--size", type=int, default=1024)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--control", action="append", default=[], metavar="NAME=VALUE")
    parser.add_argument("--output", type=Path, default=Path("build/experiments/gallery/experiments"))
    parser.add_argument("--list", action="store_true")
    args = parser.parse_args()
    if args.list:
        for name in STUDIES:
            mod = importlib.import_module(f"experiments.studies.{name}")
            print(name, mod.TITLE, json.dumps(mod.CONTROLS))
        return
    width = args.width if args.width is not None else args.size
    height = args.height if args.height is not None else args.size
    if not 256 <= width <= 2048 or not 256 <= height <= 2048:
        parser.error("Dimensions must be 256..2048")
    if not 1 <= args.jobs <= 8:
        parser.error("jobs must be 1..8")
    controls = {}
    try:
        for item in args.control:
            key, value = item.split("=", 1)
            controls[key] = float(value)
        names = STUDIES if args.study == "all" else PERLIN_STUDIES if args.study == "perlin" else (args.study,)
        for name in names:
            controls_for(importlib.import_module(f"experiments.studies.{name}"), controls)
    except (ValueError, ModuleNotFoundError) as error:
        parser.error(str(error))
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = [pool.submit(render_one, name, seed, width, height, controls, args.output)
                   for name in names for seed in args.seeds]
        for future in as_completed(futures):
            print(future.result(), flush=True)


if __name__ == "__main__":
    main()
