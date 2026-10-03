"""Build contact sheets and a local comparison gallery from actual rendered PNGs."""
import argparse
import json
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont, ImageOps

TITLES = {
    "engravings": "Field engravings", "membranes": "Growing membranes",
    "attractors": "Related attractor families", "geology": "Geological prints",
    "cells": "Cellular collage", "ecologies": "Branching ecologies", "cities": "Imagined cities",
    "perlin": "Original · Noise Flowfield", "fractal": "Original · Fractal Flame",
    "circle": "Original · Organic Growth", "fujii": "Original · Fujii Attractor",
    "galaxies": "Original · Galaxies",
    "folded_veils": "Folded veils", "branched_light": "Branched light",
    "inertial_filaments": "Inertial filaments",
}

PERLIN_GROUPS = ("experiments/folded_veils", "experiments/branched_light",
                 "experiments/inertial_filaments", "smooth/branched_light",
                 "smooth/inertial_filaments", "baseline/folded_veils",
                 "baseline/branched_light", "baseline/inertial_filaments", "originals/perlin",
                 "originals/fujii", "experiments/attractors")


def font(size):
    for candidate in ("C:/Windows/Fonts/segoeui.ttf", "DejaVuSans.ttf"):
        try:
            return ImageFont.truetype(candidate, size)
        except OSError:
            pass
    return ImageFont.load_default(size=size)


def sheet(items, title, output, grayscale=False):
    columns, tile, gap, margin, header, label = 6, 272, 14, 22, 80, 29
    rows = (len(items) + columns - 1) // columns
    width = margin * 2 + columns * tile + (columns - 1) * gap
    height = header + rows * (tile + label + gap) + margin
    canvas = Image.new("RGB", (width, height), "#f2f0ea")
    draw = ImageDraw.Draw(canvas)
    draw.text((margin, 14), title, fill="#22272c", font=font(25))
    subtitle = f"{len(items)} uncurated samples · " + ("grayscale" if grayscale else "original colors")
    draw.text((margin, 48), subtitle, fill="#626765", font=font(16))
    for index, item in enumerate(items):
        x = margin + index % columns * (tile + gap)
        y = header + index // columns * (tile + label + gap)
        with Image.open(item["absolute"]) as original:
            image = original.convert("RGB")
            if grayscale:
                image = ImageOps.grayscale(image).convert("RGB")
            image.thumbnail((tile, tile), Image.Resampling.LANCZOS)
        canvas.paste(image, (x + (tile - image.width) // 2, y + (tile - image.height) // 2))
        draw.text((x, y + tile + 6), f"Seed {item['seed']:02d}", fill="#30363a", font=font(15))
    output.parent.mkdir(parents=True, exist_ok=True)
    canvas.save(output, quality=91, subsampling=0)


PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>PFB Studio · Generator experiments</title><style>
:root{color-scheme:dark;--bg:#131617;--panel:#1b2021;--ink:#ebece6;--muted:#a8b4b1;--line:#343e3c;--accent:#b5dfbb}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.55 'Segoe UI',sans-serif}
main{max-width:1600px;margin:auto;padding:40px 32px}header{padding-bottom:26px;border-bottom:1px solid var(--line)}
.eyebrow{color:var(--accent);letter-spacing:.17em;font-size:12px}h1{font-weight:500;font-size:42px;line-height:1.15;margin:12px 0}
h2{font-weight:500;font-size:25px}p{max-width:950px;color:var(--muted)}a{color:var(--accent)}button,select{font:inherit;color:var(--ink);background:var(--panel);border:1px solid var(--line);border-radius:5px;padding:9px 12px}
button{cursor:pointer}button[aria-pressed=true]{color:#122317;background:var(--accent)}label{display:inline-flex;gap:9px;align-items:center}
.toolbar{display:flex;gap:16px;align-items:center;flex-wrap:wrap;margin:22px 0}.compare{display:grid;grid-template-columns:1fr 1fr;gap:20px}
figure{margin:0;background:var(--panel);border:1px solid var(--line);border-radius:6px;overflow:hidden}
.compare img{width:100%;height:540px;object-fit:contain;background:#101314}.compare figcaption{padding:14px}select{max-width:100%}
.grid{display:grid;grid-template-columns:repeat(6,minmax(0,1fr));gap:12px}.grid img{width:100%;aspect-ratio:1;object-fit:contain;display:block}
.grid figcaption{padding:8px 10px;font-size:13px;color:var(--muted)}.mono img.art{filter:grayscale(1)}.group{margin:38px 0}
.small{font-size:13px;color:var(--muted)}.note{border-left:3px solid var(--accent);padding-left:15px}.chips{display:flex;gap:9px;flex-wrap:wrap;margin-top:22px}.chips a{text-decoration:none;border:1px solid var(--line);border-radius:20px;padding:4px 12px}
.sheetlinks{margin:8px 0 18px}.count{color:var(--accent)}.empty{padding:60px}footer{padding:35px 0;color:var(--muted)}
@media(max-width:1000px){.grid{grid-template-columns:repeat(3,minmax(0,1fr))}.compare img{height:360px}}
@media(max-width:650px){main{padding:24px 15px}h1{font-size:32px}.compare{grid-template-columns:1fr}.grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
</style></head><body><main>
<header><div class="eyebrow">PFB STUDIO / EXPERIMENTAL BRANCH</div><h1>Generator studies. Every seed.</h1>
<p>Algorithmic studies compared with the five original generators. Every numbered sample is retained. Open an image to inspect the full-resolution PNG; use grayscale to compare structure independently of hue.</p>
<div id="counts" class="count"></div><nav class="chips" id="jump"></nav></header>
<section aria-labelledby="compare-heading"><h2 id="compare-heading">Compare the same seed</h2>
<div class="toolbar"><label>Seed <select id="seed" aria-label="Comparison seed"></select></label><button id="mono" aria-pressed="false">Grayscale</button><span class="small">Equal seed numbers identify samples; the algorithms interpret them independently.</span></div>
<div class="compare"><figure><figcaption><label>Left <select id="left" aria-label="Left generator"></select></label></figcaption><a id="left-link"><img class="art" id="left-img" alt=""></a><figcaption id="left-meta"></figcaption></figure>
<figure><figcaption><label>Right <select id="right" aria-label="Right generator"></select></label></figcaption><a id="right-link"><img class="art" id="right-img" alt=""></a><figcaption id="right-meta"></figcaption></figure></div>
<p class="small note">Originals use native dimensions and complete normal rendering, including Fractal preprocessing and bloom. Their time-limited output varies with hardware and load. Experiments use fixed algorithmic work. The comparison judges form and material, not speed or pixel equivalence.</p></section>
<div id="groups"></div><footer>Generated from saved images and per-image JSON metadata. No remote assets or services are needed.</footer></main>
<script>const groups=__DATA__;
const $=id=>document.getElementById(id), selectNames=['left','right'];
for(const id of selectNames)for(const [key,g] of Object.entries(groups)){const o=new Option(g.title,key);$(id).add(o)}
const texturePair=groups['smooth/branched_light']&&groups['experiments/branched_light'];
$('left').value=texturePair?'experiments/branched_light':groups['experiments/folded_veils']?'experiments/folded_veils':groups['experiments/attractors']?'experiments/attractors':Object.keys(groups)[0];
$('right').value=texturePair?'smooth/branched_light':groups['baseline/folded_veils']?'baseline/folded_veils':groups['experiments/folded_veils']&&groups['originals/perlin']?'originals/perlin':groups['originals/fractal']?'originals/fractal':Object.keys(groups).at(-1);
function seeds(){const previous=$('seed').value,a=groups[$('left').value],b=groups[$('right').value];const common=a.images.filter(x=>b.images.some(y=>x.seed===y.seed));$('seed').replaceChildren(...common.map(x=>new Option(String(x.seed).padStart(2,'0'),x.seed)));$('seed').disabled=!common.length;if(common.some(x=>String(x.seed)===previous))$('seed').value=previous;update()}
function update(){for(const side of selectNames){const g=groups[$(side).value],im=g.images.find(x=>x.seed===Number($('seed').value)),img=$(side+'-img'),link=$(side+'-link');if(!im){img.removeAttribute('src');img.alt='';img.style.display='none';link.removeAttribute('href');$(side+'-meta').textContent='These groups have no shared seeds. Choose two default groups or two holdout groups.';continue}img.style.display='block';img.src=im.path;img.alt=g.title+' seed '+im.seed;link.href=im.path;link.target='_blank';$(side+'-meta').textContent=g.title+' · seed '+im.seed+' · '+im.width+' × '+im.height+' · '+im.seconds.toFixed(2)+'s';}}
for(const id of selectNames)$(id).addEventListener('change',seeds);$('seed').addEventListener('change',update);seeds();
$('mono').addEventListener('click',()=>{const active=document.body.classList.toggle('mono');$('mono').setAttribute('aria-pressed',String(active))});
let counts={};for(const [key,g] of Object.entries(groups)){counts[g.kind]=(counts[g.kind]||0)+g.images.length;const sec=document.createElement('section');sec.className='group';sec.id=key.replace('/','-');const title=document.createElement('h2');title.textContent=g.title+' / '+g.images.length+' samples';sec.append(title);const links=document.createElement('div');links.className='sheetlinks';for(const [label,path] of [['Color sheet',g.sheet],['Grayscale sheet',g.gray]]){const a=document.createElement('a');a.href=path;a.textContent=label;a.target='_blank';links.append(a,document.createTextNode('  ·  '))}sec.append(links);const grid=document.createElement('div');grid.className='grid';for(const im of g.images){const fig=document.createElement('figure'),a=document.createElement('a'),img=document.createElement('img'),cap=document.createElement('figcaption');a.href=im.path;a.target='_blank';img.src=im.thumb;img.loading='lazy';img.className='art';img.alt=g.title+' seed '+im.seed;cap.textContent='Seed '+String(im.seed).padStart(2,'0');a.append(img);fig.append(a,cap);grid.append(fig)}sec.append(grid);$('groups').append(sec);const jump=document.createElement('a');jump.href='#'+sec.id;jump.textContent=g.title;$('jump').append(jump)}$('counts').textContent=Object.entries(counts).map(([k,n])=>n+' '+k+' renders').join(' · ');
</script></body></html>'''


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path("build/experiments/gallery"))
    parser.add_argument("--publish-sheets", type=Path)
    parser.add_argument("--focus-perlin", action="store_true",
                        help="Show the three black-background studies and their Perlin/Fujii/attractor references")
    args = parser.parse_args()
    root = args.root.resolve()
    groups = {}
    for kind in ("experiments", "smooth", "baseline", "originals", "holdouts"):
        for directory in sorted((root / kind).glob("*")):
            if not directory.is_dir():
                continue
            if args.focus_perlin and f"{kind}/{directory.name}" not in PERLIN_GROUPS:
                continue
            items = []
            for path in sorted(directory.glob("seed-*.png")):
                metadata = json.loads(path.with_suffix(".json").read_text(encoding="utf-8-sig"))
                thumb = root / "thumbnails" / kind / directory.name / (path.stem + ".jpg")
                thumb.parent.mkdir(parents=True, exist_ok=True)
                with Image.open(path) as image:
                    preview = image.convert("RGB")
                    preview.thumbnail((384, 384), Image.Resampling.LANCZOS)
                    preview.save(thumb, quality=89)
                items.append({"absolute": path, "path": path.relative_to(root).as_posix(),
                              "thumb": thumb.relative_to(root).as_posix(),
                              "seed": metadata["seed"], "width": metadata["width"],
                              "height": metadata["height"], "seconds": metadata["render_seconds"]})
            if not items:
                continue
            name = directory.name
            suffix = (" · holdout" if kind == "holdouts" else " · first test" if kind == "baseline"
                      else " · previous finish" if kind == "smooth" else "")
            title = TITLES.get(name, name) + suffix
            basename = f"{kind}-{name}"
            for gray in (False, True):
                filename = basename + ("-gray" if gray else "") + ".jpg"
                sheet(items, title, root / "sheets" / filename, gray)
                if args.publish_sheets:
                    target = args.publish_sheets / filename
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes((root / "sheets" / filename).read_bytes())
            for item in items:
                del item["absolute"]
            groups[f"{kind}/{name}"] = {"kind": kind, "title": title, "images": items,
                                         "sheet": f"sheets/{basename}.jpg", "gray": f"sheets/{basename}-gray.jpg"}
    if not groups:
        raise SystemExit("No rendered images found")
    if args.focus_perlin:
        groups = {key: groups[key] for key in PERLIN_GROUPS if key in groups}
    data = json.dumps(groups).replace("<", "\\u003c")
    page = PAGE
    if args.focus_perlin:
        page = page.replace("Generator studies. Every seed.", "Three Perlin studies on black.")
        page = page.replace("Algorithmic studies compared with the five original generators.",
                            "Folded veils, branched light, and inertial filaments: color carried by moving material and fine particle texture on black. Compare the new branched-light and filament deposits with their previous finishes, the first tests, and original references.")
    (root / "index.html").write_text(page.replace("__DATA__", data), encoding="utf-8")
    (root / "manifest.json").write_text(json.dumps(groups, indent=2), encoding="utf-8")
    print(f"Gallery: {root / 'index.html'}; {sum(len(g['images']) for g in groups.values())} images")


if __name__ == "__main__":
    main()
