# Generator research: learning from the originals

Research brief, 2 October 2026. Work belongs on `agent/generator-experiments`, branched from the cleaned optimization PR at `38995bc`. Magnetic Loom has been removed. The ideas below record the original proposals.

**Implementation update, 3 October:** all seven directions now have standalone seeded studies, 284 comparison images, and an [aesthetic review with complete color/grayscale seed sheets](experiments/README.md). See the [runbook](../experiments/README.md) to reproduce them. No experimental generator has been integrated into the native app.

## What the originals get right

The strongest common feature is a large space of mathematical behavior held together by deliberate visual relationships. Seeds change the process that makes the image. Color, density, texture, and framing then reveal that process. A recognizable family resemblance is valuable; repeated compositions with cosmetic changes are the failure to avoid.

| Generator | What a seed changes | What holds the image together | Source |
| --- | --- | --- | --- |
| Perlin | A typed expression tree combining vector variations, scalar projections, curve embeddings, arithmetic, and noise; also scale and trajectory smoothing. | Field direction controls color, magnitude controls opacity, and accumulated motion makes the surface. Related palette anchors keep the result coherent. | [Setup and deposition](../src/legacy/perlin.cpp), [expression grammar](../src/legacy/variations.h) |
| Fractal | A shared variation vocabulary, several related attractors, sparse function mixtures, affine coefficients, weights, and final transforms. | Shared vocabulary and nearby hues relate the separate forms. Iterated color carries orbit history. Accumulation, background, grain, and bloom produce material depth. | [Construction and rendering](../src/legacy/fractal.cpp) |
| Fujii | Signed amplitudes and frequencies, trigonometric powers, and time advance change the recurrence itself. | The orbit supplies the form; displacement supplies color. Translucent accumulation reveals folds and uneven density. | [Recurrence](../src/legacy/fujii.cpp) |
| Galaxies | Independent Fujii recurrences and positions change internal structure and arrangement. | Disk mapping, a fixed hierarchy of ten foreground sizes, and a larger background form establish a scene. Repeated circles can work when their interiors, overlaps, and placement vary. | [Attractors and composition](../src/legacy/galaxies.cpp) |
| Circle | Colony count, placement, radius, interaction distances, signed forces, falloff, and noise-driven state evolution change collective motion. | Related colors, colony scale, crowding, and age connect the marks. Fine structure develops through interaction. | [Colony rules](../src/legacy/circle.cpp) |

These are source observations. Their artistic interpretation is that local complexity and overall composition reinforce each other. Circle's appearance can suggest biology, but its implementation is a particle interaction system, not a botanical branching model. Its stored `noise_scale` is unused and does not explain its variety.

Fractal has another important ingredient: **selection before final rendering**. Its ordinary preprocessing varies coefficients, measures distinct occupied pixels, and retains the best coverage encountered. That is a rudimentary search for a viable composition. Coverage is not an aesthetic score, but the original already does more than accept the first random parameter set. See `baseApp::loop` in [fractal.cpp](../src/legacy/fractal.cpp).

## Where the ideas came from

The repository credits Dawid Alimowski's 2020 PerlinFieldBot code in [the third-party notices](../THIRD_PARTY_NOTICES.md). The author's [original public repository](https://github.com/dvalim/perlinfieldbot) independently confirms the author and license. Its [README](https://github.com/dvalim/perlinfieldbot/blob/cf22a1c678d5878b0f2a03ed07595e26719c80d7/README.md) credits FastNoise and siv::PerlinNoise, without a full artistic bibliography.

The same author's earlier **art-automata** project contains explicit inspiration comments:

| Earlier work and documented credit | What it suggests for this research |
| --- | --- |
| [Flow source, lines 1–2](https://github.com/dvalim/art-automata/blob/2d441ccffac2dfaa2536b047b69cfeda25594390/flow/src/ofApp.cpp#L1-L2) credits GenerateMe's vector-field work and links the blog; the relevant article is [Drawing vector field](https://generateme.wordpress.com/2016/04/24/drawing-vector-field/). | Compose nonlinear variations, curves, arithmetic, and noise. Discover new forms by changing the function being drawn. PFB's expression grammar closely matches this approach. |
| [Fujii source, lines 1–2](https://github.com/dvalim/art-automata/blob/2d441ccffac2dfaa2536b047b69cfeda25594390/fujii/src/ofApp.cpp#L1-L2) credits [Masaru Fujii's formulas](https://how-to-build-du-e.tumblr.com/). | A time-driven recurrence with variable amplitudes, frequencies, and powers creates a family of forms. This is a mathematical relationship to PFB's recurrence, rather than evidence of a separate artistic scene template. |
| [Flame source, lines 3–5](https://github.com/dvalim/art-automata/blob/2d441ccffac2dfaa2536b047b69cfeda25594390/field/src/flame.h#L3-L5) links the original flame paper and a 3D treatment. | Functions, transforms, and color history jointly produce an image. PFB uses this same broad algorithm family. |
| [Field source, lines 37–38](https://github.com/dvalim/art-automata/blob/2d441ccffac2dfaa2536b047b69cfeda25594390/field/src/ofApp.cpp#L37-L38) credits Inconvergent's depth-of-field work; [watercolor source, lines 1–3](https://github.com/dvalim/art-automata/blob/2d441ccffac2dfaa2536b047b69cfeda25594390/watercolor/src/ofApp.cpp#L1-L3) credits Tyler Hobbs and Kjetil Golid. | Material and image formation mattered alongside equations in the author's earlier work. These credits do not establish that PFB implements those watercolor or depth-of-field techniques. |

These are documented credits for the earlier project. The connections to PFB are our interpretation of the mathematics, not citations present in PFB's README.

There is a stronger algorithmic clue for Circle: its seventh-power radial initialization, noise-driven `mood`, and `1 - abs(mood difference)` interaction closely match GenerateMe's **Grow your own iris** article of 3 January 2017, available on the [author's homepage](https://generateme.wordpress.com/). That article credits Jared Tarbell's Happy Place and several growth-system sources. This is strong evidence of lineage by code comparison, but no explicit PFB acknowledgment was found.

The flame paper supplies a relevant design principle: preserve information about the attractor through nonlinear functions, density rendering, and structural color. PFB uses related variations, affine/final transforms, and color recurrence. Its additive SFML renderer does not implement the paper's complete log-density pipeline. [Draves and Reckase, The Fractal Flame Algorithm](https://flam3.com/flame_draves.pdf).

## Why Loom fell short

Loom fixed much of its composition before the seed had a chance to matter: regular pole rings, central strand spawning, radial fading, and a narrow range of defaults. Changing turbulence and color left the same centered pinwheel. The originals allow seeds to alter equations, interactions, or meaningful relationships inside a composition.

The mistake was also evaluative. Replay and pixel-difference tests checked software behavior; they did not establish artistic range. A few attractive renders were insufficient evidence. The entire seed sheet needed inspection before integration.

## First experiment: field engravings

Start from Perlin's strongest idea: the seed constructs a mathematical program. Give that program a different drawing vocabulary.

**Proposed appearance:** fine contour engravings with folds, broken bands, large quiet areas, and occasional dense seams. The form should remain legible at thumbnail size; close inspection should reveal variations in line spacing and weight. A restrained ink treatment would give this a different character from luminous trails.

**Construction:** generate a bounded, typed field expression; sample it into a scalar surface using a seeded projection; extract level sets; add sparse directional marks where the field supports them. Couple line weight and spacing to measured curvature and gradient. Use a shared palette and surface treatment. Discontinuities and non-finite samples need explicit handling so they do not become arbitrary streaks.

The sampled field must remain spatially stable during scouting, contour extraction, and final rendering. Some existing variations, including Julia and cartesianXY, consume fresh random draws on every evaluation. Exclude these initially, or define their randomness from coordinates and seed. Saving expression parameters alone cannot make a changing field reproducible across sample orders and resolutions.

Seeds change expression structure, projection, spatial scales, and contour placement. They should be able to produce open sweeping bands, nested pockets, fragmented folds, or sparse irregular islands. These are intended outcomes, not hand-authored scene templates or demonstrated results.

Scout a bounded set of candidates with fixed work, discarding numerical failures and near-empty/full fields. Retain candidate parameters so final rendering reproduces the chosen structure. Coverage, spacing, and concentration can diagnose failures; choosing the rule distribution remains a visual decision.

**Controls worth testing:** fold scale, level spacing, directional bias, and mark density. **Main risk:** every field becomes the same decorative topographic texture. Reject the study if grayscale thumbnails remain interchangeable or extra detail conceals weak forms.

## Second experiment: growing membranes

Combine Circle's evolving interactions with differential growth of connected contours. This keeps the interest in emergence while changing the thing being simulated and drawn.

**Proposed appearance:** thin folded membranes, asymmetric lobes, stretched seams, and layered growth traces. Begin with unequal open or closed curves, several spatial scales, and protected gaps. Growth history would supply translucency and depth; curvature or strain would influence the marks.

Hoff's differential-line implementation grows a connected contour by adding nodes and explicitly points to Nervous System's Floraform as inspiration. Different initial geometry is one source of variation. Basic growth preserves connectivity; splitting, joining, or branching would be separate extensions. [Author's implementation](https://github.com/inconvergent/differential-line), [Floraform](https://n-e-r-v-o-u-s.com/projects/sets/floraform/).

Seeds should change initial curves, local growth rates, exclusion regions, and coupling between contours. A single circle growing uniformly until the canvas is full would repeat Loom's mistake. Use bounded node counts, spatial neighbor queries, and selected growth stages for a first study.

**Controls worth testing:** growth anisotropy, repulsion range, growth duration, and history visibility. **Main risk:** tangled noodles or a uniform ruffled disk. This has greater engineering risk than field engravings because collision handling and stable growth matter.

## Alternatives retained from the broader research

| Direction | Useful source mechanism | Why it remains secondary |
| --- | --- | --- |
| Related attractor families | PFB's shared function vocabulary, extended experimentally with persistent transform sequences and occasional switches. | Plausible, but could become another Fractal preset instead of a distinct generator. |
| Geological prints | Design major terrain features before drainage and erosion; translate the hierarchy into bands and incised channels. [Mapgen4](https://www.redblobgames.com/maps/mapgen4/), [erosion research](https://arxiv.org/pdf/2210.14496) | Composition potential, but a new subject alone does not guarantee the originals' depth. Terrain simulation increases scope. |
| Cellular collage | Map L-systems determine adjacency through division, then assign geometry. The binary propagating model splits cells without merging or deletion. [Cellular layers](https://algorithmicbotany.org/papers/abop/abop-ch7.pdf) | Unequal masses and selective subdivision could work, but even tiling becomes repetitive. Cutouts would be an extension. |
| Branching ecologies | Space colonization responds to available space, point distributions, and obstacles. [Original paper](https://algorithmicbotany.org/papers/colonization.egwnp2007.pdf) | A centered root in a circular envelope easily becomes another repeated emblem. Loops require a network extension. |
| Imagined cities | Road-growth goals and constraints, followed by blocks and buildings. [Parish and Müller](https://cgl.ethz.ch/Downloads/Publications/Papers/2001/p_Par01.pdf) | District relationships could provide variety, but scene construction is substantial and the visual connection to PFB is weaker. |

These appearances and implementation assessments are design proposals. Sources support mechanisms, not a guarantee that our adaptation will make compelling artwork.

## Evidence required before integration

1. Establish reference sheets from the originals at native dimensions, with ordinary rendering allowed to complete. Include whole compositions and detail crops. Preserve their automatic settings instead of flattening every generator into one preset.
2. Give each new study the same predetermined seeds, 1 through 24. Save every result at its intended aspect and at least 1024 pixels. Show color and grayscale sheets; where supported, also render with a fixed palette to distinguish structural from color variation.
3. Inspect dominant masses, openings, folds, direction, scale hierarchy, overlap, and surface detail. A consistent identity is desirable. Recoloring, reflection, rotation, or additional grain alone do not demonstrate range.
4. Sweep low, middle, and high settings for each proposed structural control on six seeds. Confirm the named visual effect persists across the set.
5. Check eight additional seeds after fixing the initial direction, plus wide/portrait framing and 2048-pixel detail. Include weak images in the review.
6. Integrate only after the full sheet is visually convincing. Metrics for coverage, clipping, radial concentration, or near-duplicates are warnings to inspect, not quality scores.

The images reviewed so far are limited probes, not this reference study. Existing normal-mode Fujii, Galaxy, and Circle outputs use one seed, 512-square images, and roughly 2.5 seconds. Their native durations are much longer; Circle and Galaxy retain absolute-coordinate geometry that gets cropped at that size. Fractal benchmark mode omits preprocessing and bloom. Those outputs are useful for correctness checks and cannot establish the originals' mature range.

The next implementation should be a small, removable field-engraving study on this branch, followed by the complete seed-sheet review. Growing membranes is the second candidate if the first cannot earn a distinct identity. UI, production optimization, and promotion into the mainline candidate come after that visual decision.
