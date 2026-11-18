#!/usr/bin/env python3
# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only

"""Invalidate native objects when effective build configuration changes.

Make tracks source/header timestamps; this stamp covers inputs Make otherwise
misses: flags, source overrides, compiler identity, and MPFR/GMP installation.
It is a build prerequisite, never a cached test-pass result.
"""

import hashlib
import json
import os
from pathlib import Path
import shlex
import shutil
import subprocess
import sys


def file_identity(path):
    path = Path(path).resolve()
    return {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def configuration():
    values = {
        key.removeprefix("GI_BUILD_"): value.strip()
        for key, value in os.environ.items()
        if key.startswith("GI_BUILD_")
    }
    identities = {}
    for key in ("CC", "AR"):
        command = shlex.split(values[key])
        executable = shutil.which(command[0])
        if executable is None:
            raise RuntimeError(f"cannot find {key}: {command[0]}")
        path = Path(executable).resolve()
        stat = path.stat()
        identities[key] = {
            "path": str(path),
            "size": stat.st_size,
            "mtime_ns": stat.st_mtime_ns,
            "version": (
                subprocess.check_output(command + ["--version"], text=True)
                if key != "AR"
                else file_identity(path)
            ),
        }
    dependencies = []
    for prefix_key, header, library in (
        ("MPFR_PREFIX", "mpfr.h", "mpfr"),
        ("GMP_PREFIX", "gmp.h", "gmp"),
    ):
        prefix = values[prefix_key]
        if prefix:
            root = Path(prefix)
            candidates = [root / "include" / header]
            candidates += list((root / "lib").glob(f"lib{library}.*"))
            dependencies.extend(
                file_identity(p) for p in sorted(candidates) if p.is_file()
            )
    # System installations (including Linux multiarch) have no Homebrew prefix.
    compiler = shlex.split(values["CC"])
    for library in ("mpfr", "gmp"):
        for suffix in ("so", "a", "dylib"):
            located = subprocess.check_output(
                compiler + [f"-print-file-name=lib{library}.{suffix}"], text=True
            ).strip()
            if Path(located).is_file():
                dependencies.append(file_identity(located))
    return {
        "values": values,
        "tools": identities,
        "dependencies": dependencies,
        "makefiles": [
            file_identity(path) for path in shlex.split(values["GI_MAKEFILE_INPUTS"])
        ],
        "tracker": file_identity(__file__),
        "environment": {
            key: os.environ.get(key)
            for key in (
                "SDKROOT",
                "MACOSX_DEPLOYMENT_TARGET",
                "CPATH",
                "C_INCLUDE_PATH",
                "LIBRARY_PATH",
                "DEVELOPER_DIR",
            )
        },
    }


def main():
    output = Path(sys.argv[1])
    payload = json.dumps(configuration(), sort_keys=True, indent=2) + "\n"
    changed = not output.exists() or output.read_text() != payload
    if "--check" in sys.argv[2:]:
        print("changed" if changed else "unchanged")
        return
    if changed:
        # Only known Make products, never the build directory or retained evidence.
        # Remove before recording the new configuration so a failed build cannot
        # leave old objects eligible for reuse on the next invocation.
        for name in shlex.split(os.environ["GI_BUILD_PRODUCTS"]):
            for path in (Path(name), Path(name + ".d")):
                path.unlink(missing_ok=True)
        output.parent.mkdir(parents=True, exist_ok=True)
        temporary = output.with_suffix(".tmp")
        temporary.write_text(payload)
        temporary.replace(output)


if __name__ == "__main__":
    main()
