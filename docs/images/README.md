# image provenance

these are captures of relgraph itself, made on 2026-10-24. no GrafEq images,
user documents or photographs are included. the PNG files are unretouched.

## mobile app

`iphone-cardioid.png` and `iphone-editor.png` are XCTest screenshots of the
standard Flet simulator app (`org.relgraph.app`) on the installed iPhone Duo
simulator, iOS 27.1. the simulator includes the status region on the right.
these are development screenshots, not physical-device or App Store screenshots.

source revision: `9b49ccf8248f90dc865d41e750e40746cd0fee3f`, plus an experimental
project-owned editor stylesheet change enabling content overflow, container
hit testing and panning. this did not change the pictured formula, renderer or keypad. that
experiment is not evidence that long-formula touch scrolling is fixed.

the standard `deploy_ios.py simulator` workflow built and installed the app.
XCTest launched the app's bundled cardioid example, then tapped its keyboard
button. neither capture submits edits or saves a user graph. the displayed
99.2% and 99.3% statuses are ongoing refinement snapshots; the captures have no
completed-render timing claim.

## graph images

`cardioid.png` and `unit-circle.png` were made by the app's `build_previews.py`
renderer at the same source revision, with only its output directory redirected.
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
dde2cb1eed99c901a672504187b6206aecbe218474851cdeb9a1625f705a50db  iphone-cardioid.png
c4449a45056be5b2e86a3031e5d1885125bb4c20691bcebf5c05af2be2c484a9  iphone-editor.png
```

## readme gallery, 2026-10-27

The current README uses two fully classified rogue renders and three curated
gallery renders from the real application engine. See [equations and capture
records](gallery.md) for exact formulas, source example paths, settings,
classification state and reproduction commands. Existing mobile/cardioid/circle
captures above are retained; the unit circle is no longer featured in the README.

The mobile screenshots remain development refinement snapshots at the recorded
revision, not completed-render evidence. Their status is visible in the captures.
