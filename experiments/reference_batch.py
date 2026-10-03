"""Render complete native originals; never use the shortened smoke-test path."""
import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import json
from pathlib import Path
import subprocess

ORIGINALS = ("perlin", "fractal", "circle", "fujii", "galaxies")


def render_one(executable, generator, seed, root, resume):
    output = root / generator / f"seed-{seed:04d}.png"
    metadata = output.with_suffix(".json")
    if resume and output.exists() and metadata.exists():
        data = json.loads(metadata.read_text())
        if data.get("seed") == seed and data.get("mode") == "normal-native-defaults":
            return f"Already complete: {generator} {seed}"
    output.parent.mkdir(parents=True, exist_ok=True)
    result = subprocess.run([str(executable), generator, str(seed), str(output)],
                            capture_output=True, text=True, timeout=180)
    output.with_suffix(".log").write_text(result.stdout + result.stderr, encoding="utf-8")
    if result.returncode:
        raise RuntimeError(f"{generator} seed {seed} failed: {result.stderr[-1000:]}")
    return result.stdout.strip()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--executable", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("build/experiments/gallery/originals"))
    parser.add_argument("--count", type=int, default=12)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--generators", nargs="+", choices=ORIGINALS, default=ORIGINALS)
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    if not 1 <= args.count <= 100 or not 1 <= args.jobs <= 8:
        parser.error("count must be 1..100 and jobs 1..8")
    executable = args.executable.resolve(strict=True)
    root = args.output.resolve()
    with ThreadPoolExecutor(max_workers=args.jobs) as pool:
        # Interleave generators so partial progress already covers all families.
        futures = [pool.submit(render_one, executable, name, seed, root, args.resume)
                   for seed in range(1, args.count + 1) for name in args.generators]
        for future in as_completed(futures):
            print(future.result(), flush=True)


if __name__ == "__main__":
    main()
