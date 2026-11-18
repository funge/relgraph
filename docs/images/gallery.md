# gallery equations and render records

These images use relgraph’s real application engine at graphing revision `f783e6af8ac7daea7378c573e37fb584bd1a2594`. The attribution worktree changes prose only, not rendering. The source catalog is `python/graphing/data/grafeq-catalog.yaml`; app adaptations are in `apps/flet/src/examples.py`.

All images use strict domain interpretation and equal world units per pixel. White means proven absent, dark blue proven present, amber unresolved. README images may be scaled by the browser; source PNGs preserve the exact raster. These are illustration captures, not performance benchmarks.

## reproduction

Use the graphing app’s Python environment and build its shared library with `make shared`. Run the command below for each record from this repository; the helper accepts an explicit graphing checkout path. It does not launch the app or access a device.

## spike

Source: `Single Relation/Abstract/Traditionally Difficult/Spike.gqs`. Mapping: `direct`.

```text
y = (x^2-3*x)/(x-3.001)
```

Bounds: `[-10.0, 10.0, -10.0, 10.0]`. Raster: 512 × 512. State: **complete**; unresolved pixels: **0**. Capture budget: 25.0 seconds.

```sh
python docs/images/render-gallery.py /path/to/graphing --one rogue_spike --resolution 512 --seconds 25.0
```

[image](gallery/rogue_spike.png) · [capture record and SHA-256](gallery/rogue_spike.json)

## circular spike

Source: `Single Relation/Abstract/Traditionally Difficult/O Spike.gqs`. Mapping: `direct`.

```text
((x^2-3*x)/(x-3.001))^2+((y^2-3*y)/(y-3.001))^2 = 81
```

Bounds: `[-10.0, 10.0, -10.0, 10.0]`. Raster: 512 × 512. State: **complete**; unresolved pixels: **0**. Capture budget: 25.0 seconds.

```sh
python docs/images/render-gallery.py /path/to/graphing --one rogue_circular_spike --resolution 512 --seconds 25.0
```

[image](gallery/rogue_circular_spike.png) · [capture record and SHA-256](gallery/rogue_circular_spike.json)

## margarita black

Source: `Multiple Relations/Margarita.gqs`. Mapping: `component`.

```text
mod(sqrt(x^2+y^2)-7/2*atan2(y,x)+sin(x)+cos(y),pi) < pi/2
```

Bounds: `[-10.0, 10.0, -10.0, 10.0]`. Raster: 512 × 512. State: **complete**; unresolved pixels: **0**. Capture budget: 90.0 seconds.

```sh
python docs/images/render-gallery.py /path/to/graphing --one gallery_margarita_black --resolution 512 --seconds 90.0
```

[image](gallery/gallery_margarita_black.png) · [capture record and SHA-256](gallery/gallery_margarita_black.json)

## arachnid

Source: `Single Relation/Solid/Arachnid.gqs`. Mapping: `direct`.

```text
sin(x)+cos(y)+sin(x*cos(y)+y*sin(x)) > 0
```

Bounds: `[-10.0, 10.0, -10.0, 10.0]`. Raster: 256 × 256. State: **complete**; unresolved pixels: **0**. Capture budget: 90.0 seconds.

```sh
python docs/images/render-gallery.py /path/to/graphing --one gallery_arachnid --resolution 256 --seconds 90.0
```

[image](gallery/gallery_arachnid.png) · [capture record and SHA-256](gallery/gallery_arachnid.json)

## masked

Source: `Single Relation/Solid/Masked.gqs`. Mapping: `direct`.

```text
sin(min(x*sin(y),y*sin(x))) > cos(max(x*cos(y),y*cos(x)))+(2*(x-y)^2+(x+y-6)^2)/40-1/30*(12-x-y)
```

Bounds: `[-6.0, 6.0, -3.0, 9.0]`. Raster: 256 × 256. State: **complete**; unresolved pixels: **0**. Capture budget: 45.0 seconds. This closer viewport frames the same relation; its catalog bounds are `[-10.0, 10.0, -10.0, 10.0]`.

```sh
python docs/images/render-gallery.py /path/to/graphing --one gallery_masked --resolution 256 --seconds 45.0 --bounds -6 6 -3 9
```

[image](gallery/gallery_masked.png) · [capture record and SHA-256](gallery/gallery_masked.json)

## selection notes

Spike and circular spike illustrate narrow branches near poles. Margarita is one component of the source’s multi-relation example; arachnid and masked are single relations. Frontispiece and chrome were trialled but not selected: their detail remained too unresolved within the bounded rendering attempts. Digital bacteria’s body component was replaced by the more visually varied arachnid.

The README credits GrafEq’s definitions and names. That attribution does not resolve the separate question of catalog reuse permission.
