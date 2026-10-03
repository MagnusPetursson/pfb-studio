"""Unequal recursive cell division rendered as a material collage.

Source basis: Prusinkiewicz/Lindenmayer, The Algorithmic Beauty of Plants,
chapter 7 (https://algorithmicbotany.org/papers/abop/abop-ch7.pdf): division
changes adjacency before geometry is rendered. Here straight half-plane splits
retain parent regions and unequal growth; gaps, cutouts and print textures are
artistic extensions. This is not the book's map L-system or a Voronoi diagram.
"""
from __future__ import annotations

import math
import numpy as np
from PIL import Image, ImageDraw

TITLE = "Cellular collage"
DESCRIPTION = "Unequal divisions retain broad parent regions among fine, cut and printed cells."
CONTROLS = {
    "subdivision": {"default": 0.5, "label": "Local subdivision"},
    "gaps": {"default": 0.5, "label": "Seam width"},
    "cutouts": {"default": 0.5, "label": "Open cells"},
}


def _clip(poly, normal, offset):
    output = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        da, db = np.dot(a, normal)-offset, np.dot(b, normal)-offset
        if da <= 1e-9: output.append(a)
        if (da < 0) != (db < 0):
            t = da / (da-db)
            output.append((a[0]+t*(b[0]-a[0]), a[1]+t*(b[1]-a[1])))
    return output


def _area(poly):
    return abs(sum(a[0]*b[1]-b[0]*a[1] for a, b in zip(poly, poly[1:]+poly[:1]))) / 2


def _inset(poly, amount):
    out = poly[:]
    center = np.mean(poly, axis=0)
    for a, b in zip(poly, poly[1:]+poly[:1]):
        n = np.array((b[1]-a[1], a[0]-b[0]), dtype=float)
        n /= max(float(np.linalg.norm(n)), 1e-10)
        d = float(np.dot(a, n))
        if np.dot(center, n) > d: n, d = -n, -d
        out = _clip(out, n, d-amount)
        if len(out) < 3: return []
    return out


def render(seed: int, width: int, height: int, controls: dict | None = None):
    if width < 64 or height < 64:
        raise ValueError("Study dimensions must be at least 64 pixels")
    c = {k: v["default"] for k, v in CONTROLS.items()}
    c.update(controls or {})
    if any(k not in CONTROLS or not np.isfinite(v) or not 0 <= v <= 1 for k, v in c.items()):
        raise ValueError("Controls must be finite normalized values")
    rng = np.random.default_rng(seed)
    # Work in an isotropic coordinate space to keep portrait and wide studies honest.
    aspect = width / height
    palettes = [
        [(238,228,207),(45,61,65),(174,79,48),(211,157,75),(121,146,133)],
        [(232,227,212),(49,67,91),(86,121,142),(186,99,69),(170,176,153)],
        [(236,222,205),(63,69,62),(161,154,92),(194,96,80),(203,177,138)],
        [(232,226,213),(48,78,79),(120,155,148),(210,158,92),(180,102,95)],
    ]
    palette_index = int(rng.integers(len(palettes)))
    palette = palettes[palette_index]
    image = Image.new("RGB", (width*2, height*2), palette[0])
    draw = ImageDraw.Draw(image)
    scale = height*2
    margin = rng.uniform(.035, .105)
    root = [(margin*aspect, margin), ((1-margin)*aspect, margin), ((1-margin)*aspect, 1-margin), (margin*aspect, 1-margin)]
    # Clip unequal corners: the overall silhouette varies before fine subdivision.
    for corner in rng.choice(4, size=int(rng.integers(1, 4)), replace=False):
        normals = [(-1,-1), (1,-1), (1,1), (-1,1)]
        normal = np.array(normals[corner], float)
        projected = np.array(root) @ normal
        root = _clip(root, normal, float(projected.max()-rng.uniform(.025, .20)))
    base_angle = rng.uniform(-math.pi, math.pi)
    hotspots = [(rng.uniform(.1,.9)*aspect, rng.uniform(.1,.9), rng.uniform(.13,.40)) for _ in range(int(rng.integers(1,4)))]
    leaves = []
    split_count = 0
    def divide(poly, depth, family, orientation):
        nonlocal split_count
        area = _area(poly)
        center = np.mean(poly, axis=0)
        activity = max(math.exp(-((center[0]-hx)**2+(center[1]-hy)**2)/(2*hr*hr)) for hx,hy,hr in hotspots)
        target = (.004 + (1-c["subdivision"]) * .025) * (1.9-1.65*activity)
        stop = depth >= 8 or area < target or (depth > 2 and area < .18 * aspect and rng.random() < .11 + .10 * (1-activity))
        if stop:
            leaves.append((poly, depth, family, orientation))
            return
        a = orientation + (math.pi/2 if depth % 2 else 0) + rng.normal(0, .22 + .22*activity)
        normal = np.array((math.cos(a), math.sin(a)))
        projected = np.array(poly) @ normal
        offset = float(np.quantile(projected, rng.uniform(.3,.7)))
        first, second = _clip(poly, normal, offset), _clip(poly, -normal, -offset)
        if len(first)<3 or len(second)<3 or min(_area(first),_area(second)) < .0004:
            leaves.append((poly, depth, family, orientation))
            return
        split_count += 1
        for i, part in enumerate((first, second)):
            fam = family if depth > 1 else family*2+i+1
            divide(part, depth+1, fam, orientation + (rng.normal(0,.35) if depth==1 else 0))
    divide(root, 0, 0, base_angle)
    voids, textured, coarse = 0, 0, 0
    color_by_family = {f: int(rng.integers(1,5)) for _,_,f,_ in leaves}
    region_materials, open_region_ids = [], []
    for region_id, (poly, depth, family, orientation) in enumerate(leaves):
        # Removing one cell must not reroll the pigments or marks of later cells.
        # The material and cutout decisions each belong to this persistent region.
        material_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 3719, region_id]))
        cutout_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 4171, region_id]))
        index = color_by_family[family] if material_rng.random()<.62 else int(material_rng.integers(1,5))
        color = np.array(palette[index], dtype=float)
        color = color * material_rng.uniform(.87,1.02) + np.array(palette[0]) * material_rng.uniform(0,.07)
        color = tuple(int(v) for v in np.uint8(np.clip(color,0,255)))
        material = str(material_rng.choice(["flat", "hatch", "insets", "flecks"], p=[.43,.27,.15,.15]))
        region_materials.append({"region": region_id, "family": family, "palette_entry": index,
                                 "color": list(color), "material": material,
                                 "material_seed": [int(seed), 3719, region_id]})
        gap = (.001 + .006*c["gaps"]) * (1.3 if depth < 4 else .65)
        inset = _inset(poly, gap)
        if len(inset) < 3: continue
        if cutout_rng.random() < c["cutouts"] * (.17 if depth<4 else .36):
            voids += 1
            open_region_ids.append(region_id)
            if cutout_rng.random() < .55:
                pts = [(float(x*scale),float(y*scale)) for x,y in inset]
                draw.line(pts+pts[:1], fill=palette[1], width=max(1, round(scale*.00065)))
            continue
        pts = [(float(x*scale),float(y*scale)) for x,y in inset]
        draw.polygon(pts, fill=color)
        area = _area(poly)
        coarse += int(area > .06)
        if material == "flat": continue
        textured += 1
        center = np.mean(inset, axis=0)
        ink = tuple(int(.78*a+.22*b) for a,b in zip(color, palette[0] if index==1 else palette[1]))
        if material == "insets":
            for distance in np.arange(.006, .07, .006):
                inner = _inset(inset, float(distance))
                if len(inner) < 3 or _area(inner)<.0003: break
                q = [(float(x*scale),float(y*scale)) for x,y in inner]
                draw.line(q+q[:1], fill=ink, width=max(1,round(scale*.0007)))
        elif material == "hatch":
            a = orientation + material_rng.uniform(-.35,.35)
            normal = np.array((math.cos(a),math.sin(a)))
            projections = np.array(inset) @ normal
            for offset in np.arange(projections.min(), projections.max(), material_rng.uniform(.003,.007)):
                hits = []
                for va,vb in zip(inset,inset[1:]+inset[:1]):
                    da,db = np.dot(va,normal)-offset,np.dot(vb,normal)-offset
                    if da*db < 0:
                        t = da/(da-db)
                        hits.append(np.array(va)+t*(np.array(vb)-va))
                if len(hits)==2:
                    draw.line([tuple(h*scale) for h in hits],fill=ink,width=max(1,round(scale*.0006)))
        else:
            # Rejection sampling stays inside the convex cell, preserving its region.
            low,high = np.min(inset,axis=0),np.max(inset,axis=0)
            for _ in range(min(700,int(area*18000))):
                p = material_rng.uniform(low,high)
                cross = [(b[0]-a[0])*(p[1]-a[1])-(b[1]-a[1])*(p[0]-a[0]) for a,b in zip(inset,inset[1:]+inset[:1])]
                if min(cross)>=-1e-9 or max(cross)<=1e-9:
                    xx,yy = p*scale
                    r = material_rng.uniform(.0003,.0013)*scale
                    draw.ellipse((xx-r,yy-r,xx+r,yy+r),fill=ink)
    image = image.resize((width,height),Image.Resampling.LANCZOS)
    arr = np.asarray(image).astype(float)
    texture_rng = np.random.default_rng(np.random.SeedSequence([int(seed), 5639]))
    arr += texture_rng.normal(0,1.0,(height,width,1))
    return Image.fromarray(np.uint8(np.clip(arr,0,255))), {"study":"cells","seed":int(seed),"controls":c,"palette":palette_index,"cells":len(leaves),"splits":split_count,"open_cells":voids,"open_region_ids":open_region_ids,"region_materials":region_materials,"textured_cells":textured,"coarse_cells":coarse,"hotspots":[list(v) for v in hotspots],"maximum_depth":max(v[1] for v in leaves)}
