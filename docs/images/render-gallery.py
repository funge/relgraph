#!/usr/bin/env python3
# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only

"""Render README illustrations with a separate graphing application checkout.

Usage: python render-gallery.py /path/to/graphing --seconds 30 --resolution 512
Use graphing's Flet Python environment. Each case runs in a bounded subprocess.
"""
import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

CASES = (
    'rogue_spike', 'rogue_circular_spike', 'gallery_margarita_black',
    'gallery_arachnid', 'gallery_masked', 'sine_reciprocal_argument',
)


def render(args):
    root = args.graphing.resolve()
    sys.path[:0] = [str(root / 'python'), str(root / 'apps/flet/src')]
    from examples import load_examples
    from render_worker import RenderWorker
    from render_worker import make_request
    from graphing.formulas.grafeq_catalog import load_grafeq_catalog

    if args.one == 'sine_reciprocal_argument':
        # README illustration only; deliberately not an app preset.
        formula, bounds = 'y = sin(1/x)', (-1.2, 1.2, -1.2, 1.2)
        source_example, mapping = None, 'authored README example'
    else:
        item = load_examples()[args.one]
        source = load_grafeq_catalog().builtins_by_name[args.one]
        formula, bounds = item.formula, item.bounds
        source_example, mapping = source.example_path, source.mapping
    worker = RenderWorker()
    request = make_request(formula, args.bounds or bounds, args.resolution)
    worker.submit(request)
    deadline = time.monotonic() + args.seconds
    update = None
    try:
        while time.monotonic() < deadline:
            update = worker.latest()
            if update and (update.error or update.snapshot.state.value != 'active'):
                break
            time.sleep(0.02)
        if update is None or update.error:
            raise RuntimeError(f'render failed: {update}')
        output = Path(__file__).parent / 'gallery'
        output.mkdir(exist_ok=True)
        png = update.png  # Exact worker pixels: white absent, blue present, amber unresolved.
        (output / f'{args.one}.png').write_bytes(png)
        record = dict(
            name=args.one, formula=formula, bounds=bounds,
            render_bounds=request.bounds, resolution=args.resolution,
            source_example=source_example, mapping=mapping,
            state=update.snapshot.state.value, undecided=update.snapshot.undecided,
            elapsed_seconds=update.elapsed, budget_seconds=args.seconds,
            graphing_revision=subprocess.check_output(
                ['git', '-C', str(root), 'rev-parse', 'HEAD'], text=True).strip(),
            domain='strict', colors='white absent; dark blue present; amber unresolved',
            sha256=hashlib.sha256(png).hexdigest(),
        )
        (output / f'{args.one}.json').write_text(json.dumps(record, indent=2) + '\n')
        print(f'{args.one}: {record["state"]}, {record["undecided"]} unresolved', flush=True)
    finally:
        worker.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('graphing', type=Path)
    parser.add_argument('--seconds', type=float, default=30)
    parser.add_argument('--resolution', type=int, choices=(128, 256, 512), default=512)
    parser.add_argument('--one', choices=CASES)
    parser.add_argument('--bounds', type=float, nargs=4, metavar=('XMIN', 'XMAX', 'YMIN', 'YMAX'))
    args = parser.parse_args()
    if args.bounds and not args.one:
        parser.error('--bounds requires --one')
    if not 0 < args.seconds <= 120:
        parser.error('seconds must be in (0, 120]')
    if args.one:
        render(args)
    else:
        for name in CASES:
            subprocess.run([sys.executable, __file__, str(args.graphing),
                            '--seconds', str(args.seconds), '--resolution', str(args.resolution),
                            '--one', name], check=True, timeout=args.seconds + 10)


if __name__ == '__main__':
    main()
