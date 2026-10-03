"""Reproducible control auditions and mechanical checks for removable studies.

Run: python -m experiments.audit --study all --mode all --jobs 3
The default audition is seeds 1..6 at 512 square, each control at 0/.5/1.
Coordinate --jobs with other render batches: this command never starts more
than three workers, but cannot reserve slots in unrelated processes.
Checks detect reproducibility/interface problems, not artistic quality.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor, as_completed
from datetime import datetime, timezone
import hashlib
import html
import importlib
from importlib import metadata as package_metadata
import json
import os
from pathlib import Path
import platform
import time
from typing import Any

for _variable in ("OPENBLAS_NUM_THREADS", "OMP_NUM_THREADS", "MKL_NUM_THREADS"):
    os.environ.setdefault(_variable, "1")
os.environ.setdefault("MPLBACKEND", "Agg")

from experiments.render import PERLIN_STUDIES, STUDIES, controls_for, seed_list

VALUES = (0.0, 0.5, 1.0)
VALUE_LABELS = ("0", "0.5", "1")
AUDIT_VERSION = 1


def _strict_json(value: Any) -> str:
    return json.dumps(value, indent=2, allow_nan=False)


def _write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(_strict_json(value), encoding="utf-8")


def _source_hash(module: Any) -> str:
    return hashlib.sha256(Path(module.__file__).read_bytes()).hexdigest()


def _environment() -> dict[str, str]:
    result = {"python": platform.python_version()}
    for name in ("numpy", "scipy", "Pillow", "matplotlib", "aggdraw", "contourpy"):
        try:
            result[name] = package_metadata.version(name)
        except package_metadata.PackageNotFoundError:
            result[name] = "not installed"
    return result


def _stem(seed: int, value: float) -> str:
    return f"seed-{seed:04d}-value-{value:g}".replace(".", "p")


def _render_checked(name: str, seed: int, width: int, height: int,
                    controls: dict[str, float], path: Path, expected_source: str,
                    environment: dict[str, str], resume: bool) -> dict[str, Any]:
    from PIL import Image, ImageStat

    module = importlib.import_module(f"experiments.studies.{name}")
    values = controls_for(module, controls)
    actual_source = _source_hash(module)
    if actual_source != expected_source:
        raise RuntimeError(f"{name} source changed during this audit; restart the study")
    signature = {
        "audit_version": AUDIT_VERSION, "study": name, "seed": seed,
        "width": width, "height": height, "controls": values,
        "source_sha256": actual_source, "environment": environment,
    }
    common = (Path(module.__file__).with_name("perlin_common.py") if name in PERLIN_STUDIES
              else Path(__file__).with_name("common.py"))
    signature["common_source_sha256"] = hashlib.sha256(common.read_bytes()).hexdigest() if common.exists() else None
    if name in PERLIN_STUDIES:
        finish = Path(module.__file__).with_name("perlin_finish.py")
        signature["finish_source_sha256"] = hashlib.sha256(finish.read_bytes()).hexdigest()
    json_path = path.with_suffix(".json")
    if resume and path.is_file() and json_path.is_file():
        try:
            previous = json.loads(json_path.read_text(encoding="utf-8"))
            _strict_json(previous)
            if previous.get("signature") == signature:
                with Image.open(path) as image:
                    digest = hashlib.sha256(image.tobytes()).hexdigest()
                    valid = image.mode == "RGB" and image.size == (width, height)
                    varied = any(low != high for low, high in image.getextrema())
                if valid and varied and digest == previous["pixel_sha256"]:
                    return {**previous, "cache_reused": True}
        except (OSError, ValueError, KeyError, TypeError):
            pass
    started = time.perf_counter()
    image, details = module.render(seed, width, height, values)
    elapsed = time.perf_counter() - started
    if not isinstance(image, Image.Image):
        raise TypeError(f"{name} returned {type(image).__name__}, expected PIL.Image")
    if image.mode != "RGB" or image.size != (width, height):
        raise ValueError(f"{name} returned {image.mode} {image.size}, expected RGB {(width, height)}")
    if not isinstance(details, dict):
        raise TypeError(f"{name} metadata must be a dictionary")
    _strict_json(details)
    extrema = image.getextrema()
    varied = any(low != high for low, high in extrema)
    if not varied:
        raise ValueError(f"{name}, seed {seed}: every pixel has the same color")
    pixels = image.tobytes()
    if len(pixels) != width * height * 3:
        raise ValueError(f"{name}, seed {seed}: incomplete pixel output")
    result = {
        "signature": signature, "title": module.TITLE,
        "pixel_sha256": hashlib.sha256(pixels).hexdigest(),
        "render_seconds": elapsed, "image_path": str(path.resolve()),
        "channel_extrema": extrema, "channel_stddev": ImageStat.Stat(image).stddev,
        "checks": {"rgb_dimensions": True, "nonempty": True,
                   "spatially_nonuniform": varied, "strict_json": True},
        "metadata": details,
    }
    if _source_hash(module) != expected_source:
        raise RuntimeError(f"{name} source changed while rendering; restart the study")
    # Validate the complete record before writing either artifact.
    _strict_json(result)
    path.parent.mkdir(parents=True, exist_ok=True)
    image.save(path)
    _write_json(json_path, result)
    return result


def _run_task(task: dict[str, Any]) -> dict[str, Any]:
    name, kind = task["study"], task["kind"]
    root = Path(task["output"]) / name
    if kind == "control":
        path = root / task["control"] / (_stem(task["seed"], task["value"]) + ".png")
        controls = {task["control"]: task["value"]}
        width = height = task["size"]
    elif kind == "dimensions":
        path = root / "dimensions" / (task["label"] + ".png")
        controls = {}
        width, height = task["width"], task["height"]
    else:
        path = root / "checks" / "default-first.png"
        controls = {}
        width = height = task["size"]
    first = _render_checked(name, task["seed"], width, height, controls, path,
                            task["source_sha256"], task["environment"], task["resume"])
    answer = {"task": {k: v for k, v in task.items() if k != "environment"},
              "ok": True, "record": first}
    if kind == "replay":
        # Always compute the second run. Cache reuse must never turn a replay
        # assertion into a comparison of the same cached artifact with itself.
        second = _render_checked(name, task["seed"], width, height, controls,
                                 root / "checks" / "default-replay.png",
                                 task["source_sha256"], task["environment"], False)
        equal = first["pixel_sha256"] == second["pixel_sha256"]
        answer.update(ok=equal, replay_identical=equal,
                      second_sha256=second["pixel_sha256"], second_path=second["image_path"])
        _write_json(root / "checks" / "replay.json", answer)
    return answer


def _control_sheet(root: Path, name: str, control: str, label: str, seeds: list[int],
                   valid_paths: set[str]) -> Path:
    from PIL import Image, ImageDraw, ImageFont

    size, gutter, row_label, header = 320, 12, 64, 78
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 17)
        small = ImageFont.truetype("DejaVuSans.ttf", 14)
    except OSError:
        font, small = ImageFont.load_default(size=17), ImageFont.load_default(size=14)
    sheet = Image.new("RGB", (row_label + 3 * (size + gutter), header + len(seeds) * (size + gutter)), "#eceae5")
    draw = ImageDraw.Draw(sheet)
    draw.text((12, 10), f"{name} / {label} | other controls at their defaults", fill="#222222", font=font)
    for column, value_label in enumerate(VALUE_LABELS):
        draw.text((row_label + column * (size + gutter) + 5, 47), f"value {value_label}", fill="#222222", font=font)
    for row, seed in enumerate(seeds):
        y = header + row * (size + gutter)
        draw.text((8, y + 12), f"seed\n{seed}", fill="#222222", font=small)
        for column, value in enumerate(VALUES):
            x = row_label + column * (size + gutter)
            path = root / name / control / (_stem(seed, value) + ".png")
            try:
                if str(path.resolve()) not in valid_paths:
                    raise OSError("No successful render in this audit; ignore older artifacts")
                with Image.open(path) as image:
                    thumbnail = image.convert("RGB").resize((size, size), Image.Resampling.LANCZOS)
                sheet.paste(thumbnail, (x, y))
            except OSError:
                draw.rectangle((x, y, x + size, y + size), fill="#efd0c8")
                draw.text((x + 18, y + 18), "Missing / failed render", fill="#792d27", font=small)
    output = root / name / control / "contact-sheet.png"
    output.parent.mkdir(parents=True, exist_ok=True)
    sheet.save(output)
    return output


def _comparison(results: list[dict[str, Any]], names: list[str], schemas: dict, seeds: list[int]) -> list[dict]:
    by_key = {}
    for result in results:
        task = result["task"]
        if result["ok"] and task["kind"] == "control":
            by_key[(task["study"], task["control"], task["seed"], task["value"])] = result["record"]["pixel_sha256"]
    report = []
    for name in names:
        for control in schemas[name]:
            rows = []
            for seed in seeds:
                hashes = [by_key.get((name, control, seed, value)) for value in VALUES]
                if None in hashes:
                    rows.append({"seed": seed, "complete": False})
                    continue
                pairs = [[VALUES[a], VALUES[b]] for a, b in ((0, 1), (1, 2), (0, 2)) if hashes[a] == hashes[b]]
                rows.append({"seed": seed, "complete": True,
                             "all_three_identical": len(set(hashes)) == 1,
                             "identical_pairs": pairs, "pixel_sha256": hashes})
            report.append({"study": name, "control": control, "rows": rows,
                           "no_effect_seeds": [r["seed"] for r in rows if r.get("all_three_identical")],
                           "partially_identical_seeds": [r["seed"] for r in rows if r.get("identical_pairs")]})
    return report


def _index(root: Path, reports: list[dict], sheets: list[Path], results: list[dict]) -> None:
    entries = []
    for path in sheets:
        relative = path.relative_to(root).as_posix()
        label = " / ".join(path.relative_to(root).parts[:2])
        entries.append(f'<article><h2>{html.escape(label)}</h2><a href="{relative}"><img src="{relative}" loading="lazy"></a></article>')
    dimension_entries = []
    for result in results:
        if result["ok"] and result["task"]["kind"] == "dimensions":
            path = Path(result["record"]["image_path"])
            relative = path.relative_to(root.resolve()).as_posix()
            label = f'{result["task"]["study"]} / {result["task"]["label"]}'
            dimension_entries.append(f'<article><h2>{html.escape(label)}</h2><a href="{relative}"><img src="{relative}" loading="lazy"></a></article>')
    warnings = [f'{r["study"]}/{r["control"]}: identical values on seeds {r["partially_identical_seeds"]}'
                for r in reports if r["partially_identical_seeds"]]
    failures = sum(not r["ok"] for r in results)
    body = f"""<!doctype html><html><meta charset="utf-8"><title>Study control audit</title>
<style>body{{margin:32px;background:#171b1e;color:#eee;font:15px system-ui}}a{{color:#9cceee}}
.grid{{display:grid;grid-template-columns:repeat(auto-fit,minmax(330px,1fr));gap:24px}}
article{{min-width:0}}h2{{font-size:16px}}img{{width:100%;height:auto;background:#eee}}</style>
<h1>Control auditions</h1><p>Rows: seeds. Columns: 0, 0.5, 1. Other controls use declared defaults.
Click a sheet for full resolution. Hash comparisons and nonuniform-output checks are mechanical checks, not art scores.</p>
<p>{len(results)} tasks; {failures} failures. <a href="audit-summary.json">Full JSON report</a></p>
<p>{html.escape('; '.join(warnings) if warnings else 'No completed control triplet has an identical pair.')}</p>
<div class="grid">{''.join(entries)}</div><h1>Framing and detail</h1><div class="grid">{''.join(dimension_entries)}</div></html>"""
    (root / "index.html").write_text(body, encoding="utf-8")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--study", choices=("all", *STUDIES), default="all")
    parser.add_argument("--mode", choices=("all", "controls", "checks", "dimensions"), default="all")
    parser.add_argument("--seeds", type=seed_list, default=seed_list("1:6"))
    parser.add_argument("--size", type=int, default=512)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--output", type=Path, default=Path("build/experiments/controls"))
    parser.add_argument("--resume", action="store_true", help="Reuse only source/environment/hash-validated render artifacts")
    args = parser.parse_args(argv)
    if not 1 <= args.jobs <= 3:
        parser.error("jobs must be 1..3; account for other running render batches")
    if not 64 <= args.size <= 2048:
        parser.error("size must be 64..2048")
    names = list(STUDIES if args.study == "all" else (args.study,))
    started_at = datetime.now(timezone.utc).isoformat()
    environment = _environment()
    schemas, sources = {}, {}
    try:
        for name in names:
            module = importlib.import_module(f"experiments.studies.{name}")
            if not callable(module.render) or not isinstance(module.TITLE, str) or not isinstance(module.CONTROLS, dict):
                raise ValueError(f"{name} does not expose the study interface")
            controls_for(module, {})
            for control, spec in module.CONTROLS.items():
                if not control or Path(control).name != control or "/" in control or "\\" in control:
                    raise ValueError(f"Unsafe control name: {control!r}")
                if not isinstance(spec.get("label"), str):
                    raise ValueError(f"{name}/{control} needs a label")
            schemas[name] = module.CONTROLS
            sources[name] = _source_hash(module)
    except (ModuleNotFoundError, AttributeError, ValueError) as error:
        parser.error(str(error))
    tasks = []
    for name in names:
        shared = {"study": name, "output": str(args.output), "size": args.size,
                  "source_sha256": sources[name], "environment": environment, "resume": args.resume}
        if args.mode in ("all", "checks"):
            tasks.append({**shared, "kind": "replay", "seed": 1})
        if args.mode in ("all", "controls"):
            for control in schemas[name]:
                for seed in args.seeds:
                    for value in VALUES:
                        tasks.append({**shared, "kind": "control", "control": control, "seed": seed, "value": value})
        if args.mode in ("all", "dimensions"):
            for label, seed, width, height in (("portrait-seed-0002-512x768", 2, 512, 768),
                                                ("wide-seed-0002-768x512", 2, 768, 512),
                                                ("detail-seed-0003-2048x2048", 3, 2048, 2048)):
                tasks.append({**shared, "kind": "dimensions", "label": label, "seed": seed, "width": width, "height": height})
    results = []
    args.output.mkdir(parents=True, exist_ok=True)
    print(f"Audit: {len(tasks)} tasks, {args.jobs} worker(s), studies={','.join(names)}", flush=True)
    with ProcessPoolExecutor(max_workers=args.jobs) as pool:
        futures = {pool.submit(_run_task, task): task for task in tasks}
        for future in as_completed(futures):
            task = futures[future]
            try:
                result = future.result()
            except Exception as error:
                result = {"task": {k: v for k, v in task.items() if k != "environment"},
                          "ok": False, "error": f"{type(error).__name__}: {error}"}
            results.append(result)
            suffix = result.get("error", "")
            print(f"[{len(results)}/{len(tasks)}] {'PASS' if result['ok'] else 'FAIL'} "
                  f"{task['study']} {task['kind']} seed={task['seed']} "
                  f"{task.get('control', task.get('label', ''))} {task.get('value', '')} {suffix}", flush=True)
            # A progress file leaves readable evidence after interruptions.
            _write_json(args.output / "audit-progress.json", {
                "started_at": started_at, "tasks_total": len(tasks), "tasks_completed": len(results),
                "failures": [r for r in results if not r["ok"]], "last_task": task,
            })
    reports, sheets = [], []
    if args.mode in ("all", "controls"):
        reports = _comparison(results, names, schemas, args.seeds)
        valid_paths = {r["record"]["image_path"] for r in results if r["ok"]}
        for name in names:
            for control, spec in schemas[name].items():
                sheets.append(_control_sheet(args.output, name, control, spec["label"], args.seeds, valid_paths))
    summary = {
        "audit_version": AUDIT_VERSION, "started_at": started_at,
        "finished_at": datetime.now(timezone.utc).isoformat(), "mode": args.mode,
        "studies": names, "seeds": args.seeds, "size": args.size, "jobs": args.jobs,
        "environment": environment, "source_sha256": sources,
        "tasks_total": len(tasks), "tasks_passed": sum(r["ok"] for r in results),
        "failures": [r for r in results if not r["ok"]],
        "control_comparisons": reports, "contact_sheets": [str(p.resolve()) for p in sheets],
        "results": sorted(results, key=lambda r: _strict_json(r["task"])),
        "interpretation": "Identical hashes flag possible ineffective controls; different hashes do not demonstrate a useful visual effect. Nonuniformity is not an aesthetic score.",
    }
    _write_json(args.output / "audit-summary.json", summary)
    # Keep previous per-study/mode evidence when studies become ready at
    # different times. A final --study all --resume consolidates the whole set.
    _write_json(args.output / f"audit-summary-{args.study}-{args.mode}.json", summary)
    _index(args.output, reports, sheets, results)
    print(f"Complete: {summary['tasks_passed']}/{len(tasks)} passed; report {args.output / 'audit-summary.json'}", flush=True)
    for report in reports:
        if report["partially_identical_seeds"]:
            print(f"CHECK CONTROL: {report['study']}/{report['control']} identical pairs on seeds {report['partially_identical_seeds']}", flush=True)
    return 1 if summary["failures"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
