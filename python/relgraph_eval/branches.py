# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only

"""Bounded Tupper §12 partial branch maps; forgetting a map only widens."""

from __future__ import annotations

BranchMap = tuple[tuple[object, int], ...]
BRANCH_MAP_MAX_ENTRIES = 16


def merge_branch_maps(left: BranchMap, right: BranchMap) -> BranchMap | None:
    """Return a compatible union, None on conflict, or empty on budget overflow."""
    if not left:
        return right
    if not right or left is right:
        return left
    additions = []
    for site, choice in right:
        for old_site, old_choice in left:
            if site is old_site:
                if choice != old_choice:
                    return None
                break
        else:
            additions.append((site, choice))
    if len(left) + len(additions) > BRANCH_MAP_MAX_ENTRIES:
        return ()
    return left + tuple(additions) if additions else left


def branch_choice(
    inherited: BranchMap, site: object | None, choice: int | None
) -> BranchMap:
    if site is None or choice is None:
        return inherited
    result = merge_branch_maps(inherited, ((site, choice),))
    # A caller without enough provenance may forget information, never values.
    return () if result is None else result
