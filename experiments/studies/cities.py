"""A road-growth study drawn as a two-dimensional architectural plan.

Source basis: Parish and Mueller, Procedural Modeling of Cities (2001),
https://cgl.ethz.ch/Downloads/Publications/Papers/2001/p_Par01.pdf : distinguish
road-growth goals from local constraints, then develop the intervening land.
This original study uses district axes, terrain, segment intersections and
clearance checks. It is not a reproduction of their L-system or a city simulator.
"""
from __future__ import annotations

import heapq
import math
from collections import defaultdict

import numpy as np
from PIL import Image, ImageDraw
from scipy.ndimage import gaussian_filter, zoom, distance_transform_edt, label

TITLE = "Imagined cities"
DESCRIPTION = "Districts grow along constrained streets around waterways, parks and shared squares."
CONTROLS = {
    "density": {"default": 0.5, "label": "Street density"},
    "water": {"default": 0.5, "label": "Waterway breadth"},
    "order": {"default": 0.5, "label": "Street alignment"},
}


def _cross(a, b):
    return a[0]*b[1]-a[1]*b[0]


def _intersection(a,b,c,d):
    ab,cd = (b[0]-a[0],b[1]-a[1]),(d[0]-c[0],d[1]-c[1])
    determinant = _cross(ab,cd)
    if abs(determinant)<1e-9: return None
    ca = (c[0]-a[0],c[1]-a[1])
    t,u = _cross(ca,cd)/determinant,_cross(ca,ab)/determinant
    if .025 < t <= 1 and -.001 <= u <= 1.001:
        return t,(a[0]+t*ab[0],a[1]+t*ab[1])
    return None


def render(seed: int, width: int, height: int, controls: dict | None = None):
    if width < 64 or height < 64:
        raise ValueError("Study dimensions must be at least 64 pixels")
    c = {k:v["default"] for k,v in CONTROLS.items()}
    c.update(controls or {})
    if any(k not in CONTROLS or not np.isfinite(v) or not 0<=v<=1 for k,v in c.items()):
        raise ValueError("Controls must be finite normalized values")
    rng = np.random.default_rng(seed)
    # A fixed design plane makes road topology independent of output resolution.
    n = 700
    nx,ny = max(180,round(n*width/max(width,height))),max(180,round(n*height/max(width,height)))
    yy,xx = np.mgrid[0:ny,0:nx]
    angle = rng.uniform(0,math.pi)
    u = (xx-nx/2)*math.cos(angle)+(yy-ny/2)*math.sin(angle)
    v = -(xx-nx/2)*math.sin(angle)+(yy-ny/2)*math.cos(angle)
    terrain = zoom(rng.normal(size=(7,7)),(ny/7,nx/7),order=3)[:ny,:nx]
    terrain = gaussian_filter(terrain,3)
    terrain /= max(float(terrain.std()),1e-9)
    bend = rng.uniform(30,100)*np.sin(u/rng.uniform(120,260)+rng.uniform(0,math.tau))
    water_offset = rng.uniform(-.35,.35)*min(nx,ny)
    water_kind = rng.choice(["river","estuary","coast"])
    if water_kind=="coast":
        water = v > water_offset + bend + terrain*12 + 65 + (.5-c["water"])*160
    else:
        breadth = 7+31*c["water"]
        if water_kind=="estuary": breadth = breadth+np.maximum(u,0)*rng.uniform(.12,.27)
        water = np.abs(v-water_offset-bend-terrain*8)<breadth
    land = ~water
    land[:18]=False;land[-18:]=False;land[:,:18]=False;land[:,-18:]=False
    shore_distance = distance_transform_edt(~water)
    candidates = np.argwhere(land & (shore_distance>26) & (xx>nx*.1) & (xx<nx*.9) & (yy>ny*.1) & (yy<ny*.9))
    if not len(candidates): raise RuntimeError("Terrain did not leave usable city land")
    district_count = int(rng.integers(2,6))
    districts = []
    for _ in range(1000):
        y,x = candidates[int(rng.integers(len(candidates)))]
        if all(math.hypot(x-d[0],y-d[1])>min(nx,ny)*.17 for d in districts):
            districts.append((float(x),float(y),float(angle+rng.normal(0,.25+(1-c["order"])*.75)),float(rng.uniform(95,200))))
        if len(districts)==district_count: break
    district_count = len(districts)
    urbanity = np.zeros((ny,nx))
    nearest = np.zeros((ny,nx),dtype=np.int32)
    nearest_dist = np.full((ny,nx),np.inf)
    for i,(x,y,a,radius) in enumerate(districts):
        d = (xx-x)**2+(yy-y)**2
        urbanity += np.exp(-d/(2*radius*radius))
        take=d<nearest_dist;nearest[take]=i;nearest_dist[take]=d[take]
    urbanity *= np.clip(1.2-.12*np.maximum(terrain,0),.4,1.2)
    edges = []
    buckets = defaultdict(list)
    nodes = defaultdict(list)
    cell_size = 36
    def keys(a,b,pad=0):
        for iy in range(int((min(a[1],b[1])-pad)//cell_size),int((max(a[1],b[1])+pad)//cell_size)+1):
            for ix in range(int((min(a[0],b[0])-pad)//cell_size),int((max(a[0],b[0])+pad)//cell_size)+1):
                yield ix,iy
    def add(a,b,major=False):
        index=len(edges);edges.append((a,b,major))
        for key in keys(a,b): buckets[key].append(index)
        for point in (a,b): nodes[(int(point[0]//cell_size),int(point[1]//cell_size))].append(point)
    def inside(point):
        return 18<point[0]<nx-18 and 18<point[1]<ny-18
    # Connect district goals first. Short water crossings become deliberate bridges.
    connected = {0}
    bridge_count = 0
    for _ in range(district_count-1):
        _,i,j=min((math.hypot(districts[i][0]-districts[j][0],districts[i][1]-districts[j][1]),i,j) for i in connected for j in range(district_count) if j not in connected)
        a,b=districts[i][:2],districts[j][:2]
        distance=math.dist(a,b)
        count=max(2,int(distance/25))
        dx,dy=b[0]-a[0],b[1]-a[1]
        curvature=rng.uniform(-.15,.15)
        points=[(a[0]+dx*t-dy*curvature*math.sin(math.pi*t),a[1]+dy*t+dx*curvature*math.sin(math.pi*t)) for t in np.linspace(0,1,count+1)]
        for p,q in zip(points,points[1:]):
            add(p,q,True)
            bridge_count += int(water[int((p[1]+q[1])/2),int((p[0]+q[0])/2)])
        connected.add(j)
    queue=[];serial=0
    for i,(x,y,a,radius) in enumerate(districts):
        for direction in range(4):
            heapq.heappush(queue,(0.,serial,(x,y),a+direction*math.pi/2,i,0));serial+=1
    step=39-17*c["density"]
    maximum=int(520+950*c["density"])
    rejected=0
    while queue and len(edges)<maximum:
        priority,_,a,direction,family,depth=heapq.heappop(queue)
        if depth>28: continue
        d = direction+rng.normal(0,.015+(1-c["order"])*.07)
        length=step*rng.uniform(.85,1.15)
        b=(a[0]+math.cos(d)*length,a[1]+math.sin(d)*length)
        if not inside(b): rejected+=1;continue
        bx,by=int(b[0]),int(b[1])
        midpoint=(int((a[0]+b[0])/2),int((a[1]+b[1])/2))
        if not land[by,bx] or not land[midpoint[1],midpoint[0]]:
            rejected+=1;continue
        if depth>3 and rng.random()>min(.985,float(urbanity[by,bx])*.9+.20): continue
        # Snap junctions, stop upon a crossing, reject tiny parallel slivers.
        nearby_nodes=[p for key in keys(b,b,step*.42) for p in nodes.get(key,())]
        options=[p for p in nearby_nodes if math.dist(p,a)>step*.42 and math.dist(p,b)<step*.35]
        stop=False
        if options:
            b=min(options,key=lambda p:math.dist(p,b));stop=True
        indexes={i for key in keys(a,b,step*.2) for i in buckets.get(key,())}
        intersections=[]
        for index in indexes:
            p,q,_=edges[index]
            hit=_intersection(a,b,p,q)
            if hit: intersections.append(hit)
        if intersections:
            _,b=min(intersections,key=lambda h:h[0]);stop=True
        if math.dist(a,b)<step*.34: rejected+=1;continue
        parallel=False
        for index in indexes:
            p,q,_=edges[index]
            if min(math.dist(a,p),math.dist(a,q))<1: continue
            vx,vy=q[0]-p[0],q[1]-p[1]
            ll=vx*vx+vy*vy
            t=max(0,min(1,((b[0]-p[0])*vx+(b[1]-p[1])*vy)/max(ll,1e-9)))
            distance=math.hypot(b[0]-p[0]-t*vx,b[1]-p[1]-t*vy)
            if distance<step*.22 and abs(vx*math.cos(d)+vy*math.sin(d))>math.sqrt(ll)*.85:
                parallel=True;break
        if parallel: rejected+=1;continue
        add(a,b)
        if stop: continue
        directions=[d]
        if rng.random()<.84: directions.append(d+math.pi/2)
        if rng.random()<.73: directions.append(d-math.pi/2)
        for dd in directions:
            heapq.heappush(queue,(priority+rng.uniform(.7,1.4),serial,b,dd,family,depth+1));serial+=1
    paper=np.array((239,234,220),float)
    # Palette is a seed property, independent of how many road proposals ran.
    material_rng=np.random.default_rng(np.random.SeedSequence([int(seed),9153]))
    water_palette_index=int(material_rng.integers(3))
    water_color=np.array([(166,192,196),(178,194,184),(181,194,204)][water_palette_index],float)
    ground=np.tile(paper,(ny,nx,1))
    ground+=terrain[...,None]*1.4
    ground[water]=water_color
    plan=Image.fromarray(np.uint8(np.clip(ground,0,255)))
    draw=ImageDraw.Draw(plan)
    # Parallel shoreline traces emphasize inlets without overwhelming the street plan.
    water_distance=distance_transform_edt(water)
    arr=np.asarray(plan).copy()
    for level in (4,9,15,23):
        stripe=water & (abs(water_distance-level)<.45)
        arr[stripe]=np.uint8(water_color*.93)
    plan=Image.fromarray(arr);draw=ImageDraw.Draw(plan)
    roadmask=Image.new("L",(nx,ny));rdraw=ImageDraw.Draw(roadmask)
    for a,b,major in edges:
        rdraw.line((a,b),fill=255,width=8 if major else 5)
    available=land & (np.asarray(roadmask)==0)
    components,total=label(available)
    sizes=np.bincount(components.ravel())
    parks=[]
    building_area=available.copy()
    for number in range(1,total+1):
        if 85<sizes[number]<3000 and rng.random()<.12:
            region=components==number
            parks.append(number);building_area[region]=False
            arr=np.asarray(plan).copy();arr[region]=(195,203,176);plan=Image.fromarray(arr)
    draw=ImageDraw.Draw(plan)
    road_distance=distance_transform_edt(available)
    building_count=0
    for family,(cx,cy,orientation,radius) in enumerate(districts):
        cs,sn=math.cos(orientation),math.sin(orientation)
        spacing=rng.uniform(10,15)
        for gy in np.arange(-max(nx,ny),max(nx,ny),spacing):
            for gx in np.arange(-max(nx,ny),max(nx,ny),spacing):
                x,y=cx+gx*cs-gy*sn,cy+gx*sn+gy*cs
                ix,iy=int(x),int(y)
                if not (0<=ix<nx and 0<=iy<ny) or nearest[iy,ix]!=family or not building_area[iy,ix]: continue
                if road_distance[iy,ix]>spacing*1.8 or urbanity[iy,ix]<.26 or rng.random()>min(.98,float(urbanity[iy,ix])): continue
                # Buildings must clear every corner, roads, water, and protected parks.
                bw,bh=spacing*rng.uniform(.46,.80),spacing*rng.uniform(.42,.83)
                points=[(x+dx*cs-dy*sn,y+dx*sn+dy*cs) for dx,dy in [(-bw/2,-bh/2),(bw/2,-bh/2),(bw/2,bh/2),(-bw/2,bh/2)]]
                if any(not (0<=px<nx and 0<=py<ny) or not building_area[int(py),int(px)] or road_distance[int(py),int(px)]<1.5 for px,py in points): continue
                tone=int(rng.integers(0,5));base=[(158,145,126),(169,154,131),(188,174,148),(141,146,137),(187,159,130)][tone]
                draw.polygon(points,fill=base,outline=(113,111,98))
                if bw>7 and bh>7 and rng.random()<.3:
                    inner=[(x+(px-x)*.40,y+(py-y)*.40) for px,py in points]
                    draw.polygon(inner,fill=tuple(np.uint8(paper)))
                building_count+=1
    # Roads are paper-colored cuts with a thin architectural outline.
    for a,b,major in edges:
        draw.line((a,b),fill=(99,112,109),width=7 if major else 4)
        draw.line((a,b),fill=(246,242,226),width=5 if major else 2)
    for cx,cy,orientation,radius in districts:
        r=rng.uniform(8,14)
        draw.ellipse((cx-r-1,cy-r-1,cx+r+1,cy+r+1),fill=(107,123,115))
        draw.ellipse((cx-r,cy-r,cx+r,cy+r),fill=(221,215,191))
        draw.ellipse((cx-2,cy-2,cx+2,cy+2),fill=(112,129,111))
    # Sparse park trees, bounded to actual protected cells.
    for number in parks:
        ys,xs=np.where(components==number)
        for index in rng.choice(len(xs),size=min(len(xs)//60,45),replace=False):
            x,y=int(xs[index]),int(ys[index]);r=1.6
            draw.ellipse((x-r,y-r,x+r,y+r),fill=(127,153,127))
    plan=plan.resize((width,height),Image.Resampling.LANCZOS)
    arr=np.asarray(plan).astype(float)+material_rng.normal(0,.65,(height,width,1))
    return Image.fromarray(np.uint8(np.clip(arr,0,255))), {"study":"cities","seed":int(seed),"controls":c,"districts":[list(v) for v in districts],"district_count":district_count,"water_kind":str(water_kind),"water_fraction":float(np.mean(water)),"water_palette_index":water_palette_index,"water_color":water_color.astype(int).tolist(),"road_segments":len(edges),"rejected_proposals":rejected,"bridge_segments":bridge_count,"building_count":building_count,"park_blocks":len(parks)}
