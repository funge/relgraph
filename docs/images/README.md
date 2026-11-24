# image provenance

these are genuine relgraph captures. no GrafEq images, user documents or
photographs are included. the PNG files are unretouched.

## mobile app

`iphone-cardioid.png` and `iphone-editor.png` now use the standard iPhone 17 Pro /
iOS 27.0 XCTest captures made on 2026-11-11, from the same source as TestFlight
727. the simulator helper used development build number 696. the standard status
bar was set to 9:41 with full Wi-Fi and battery. the cardioid is fully rendered;
the second image shows the actual mathematical editor. neither shows Duo UI or
the later 1.1 layered-editing polish.

the earlier Duo/iOS 27.1 captures were replaced on 2026-11-24; their provenance
and hashes remain in git history before `672ca23`.

## graph images

`cardioid.png` and `unit-circle.png` were made by the app's `build_previews.py`
renderer at source revision `9b49ccf8248f90dc865d41e750e40746cd0fee3f`,
with only its output directory redirected.
the editor stylesheet does not participate in these renders. both use strict
domain interpretation and 512 × 512 pixels.

| image | authored relation | bounds (xmin, xmax, ymin, ymax) | result |
| --- | --- | --- | --- |
| cardioid | `(x^2 + y^2 + y)^2 <= x^2 + y^2` | `(-1.75, 1.75, -2.5, 1)` | active; 1,171 unresolved pixels after the 15-second capture budget |
| unit circle | `x*x + y*y = 1` | `(-1.5, 1.5, -1.5, 1.5)` | complete; zero unresolved pixels within the 5-second capture budget |

these were illustration captures during other development activity, not
performance benchmarks. red in the circle image represents certified curve
pixels; it does not imply an unresolved result.

## SHA-256

```text
88f64b4dca0974d15906eb85c282174ffe035a7a433cf5482b7b7d6d6ba7be9f  cardioid.png
b456dfc78ee536a6613510619150c71d19d88fa018a621ad907deaacf2cacc11  unit-circle.png
9a7db733e5baca2ab1960e1b4a71296cbd378b8129c6475c3e9e3dc376c02e6e  iphone-cardioid.png
09ac05d98521d2936200828fc7e0cfd6fd405312bbb4660aacbfe2886899a4b9  iphone-editor.png
```

## readme gallery, updated 2026-11-24

the current README uses a pole example, reciprocal-argument sine and three curated
gallery renders from the real application engine. See [equations and capture
records](gallery.md) for exact formulas, source example paths, settings,
classification state and reproduction commands. Existing mobile/cardioid/circle
captures above are retained; the unit circle is no longer featured in the README.

the mobile screenshots have separate provenance above; graph capture timings
are not app responsiveness benchmarks.
