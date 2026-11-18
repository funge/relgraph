#!/usr/bin/env bash
# Copyright (c) 2026 John Funge
# SPDX-License-Identifier: AGPL-3.0-only


set -euo pipefail

usage() {
    echo "usage: $0 [--mode all|optimized|debug|sanitizer] [--output PATH]"
}

mode=all
output=build/native-numerical-qualification.txt

while (($# > 0)); do
    case "$1" in
        --mode)
            if (($# < 2)); then
                usage >&2
                exit 2
            fi
            mode=$2
            shift 2
            ;;
        --output)
            if (($# < 2)); then
                usage >&2
                exit 2
            fi
            output=$2
            shift 2
            ;;
        --help|-h)
            usage
            exit 0
            ;;
        *)
            usage >&2
            exit 2
            ;;
    esac
done

case "$mode" in
    all|optimized|debug|sanitizer)
        ;;
    *)
        usage >&2
        exit 2
        ;;
esac

compiler=${CC:-cc}
task_temp=$(mktemp -d)
task_log="$task_temp/qualification.txt"

cleanup() {
    rm -rf "$task_temp"
}
trap cleanup EXIT

dependency_version() {
    local dependency=$1
    if command -v pkg-config >/dev/null 2>&1 \
        && pkg-config --exists "$dependency"; then
        pkg-config --modversion "$dependency"
        return
    fi
    if command -v brew >/dev/null 2>&1; then
        brew list --versions "$dependency" 2>/dev/null || echo unknown
        return
    fi
    echo unknown
}

compiler_version() {
    local selected_compiler=$1
    local -a compiler_command
    local first_line
    read -r -a compiler_command <<< "$selected_compiler"
    first_line=$("${compiler_command[@]}" --version | sed -n '1p')
    echo "$first_line"
}

run_mode() {
    local selected_mode=$1
    local cflags
    local ldflags=
    local started=$SECONDS

    case "$selected_mode" in
        optimized)
            cflags="-std=c11 -O2 -g -Wall -Wextra -Wpedantic -fno-fast-math -frounding-math"
            ;;
        debug)
            cflags="-std=c11 -O0 -g3 -Wall -Wextra -Wpedantic -fno-fast-math -frounding-math"
            ;;
        sanitizer)
            cflags="-std=c11 -O1 -g -Wall -Wextra -Wpedantic -fno-fast-math -frounding-math -fno-omit-frame-pointer -fsanitize=address,undefined"
            ldflags="-fsanitize=address,undefined"
            ;;
    esac

    echo
    echo "## $selected_mode"
    echo "CFLAGS=$cflags"
    echo "LDFLAGS=$ldflags"
    local build_dir=build
    if [[ "$selected_mode" != optimized ]]; then
        build_dir="build/qualification/$selected_mode"
    fi
    echo "BUILD_DIR=$build_dir"
    if [[ "$selected_mode" == sanitizer ]]; then
        local asan_options=${ASAN_OPTIONS:-}
        if [[ -z "$asan_options" ]]; then
            if [[ $(uname -s) == Darwin ]]; then
                asan_options=halt_on_error=1
            else
                asan_options=detect_leaks=1:halt_on_error=1
            fi
        fi
        ASAN_OPTIONS=$asan_options \
        UBSAN_OPTIONS=${UBSAN_OPTIONS:-halt_on_error=1:print_stacktrace=1} \
        CC="$compiler" CFLAGS="$cflags" \
        LDFLAGS="$ldflags" make BUILD_DIR="$build_dir" test
    else
        CC="$compiler" CFLAGS="$cflags" \
        LDFLAGS="$ldflags" make BUILD_DIR="$build_dir" test
    fi
    echo "mode_seconds=$((SECONDS - started))"
}

run_qualification() {
    local compiler_identity
    compiler_identity=$(compiler_version "$compiler")
    echo "# Native numerical qualification"
    echo
    echo "commit=$(git rev-parse HEAD)"
    echo "platform=$(uname -s)"
    echo "architecture=$(uname -m)"
    echo "compiler=$compiler_identity"
    echo "mpfr=$(dependency_version mpfr)"
    echo "gmp=$(dependency_version gmp)"
    echo "requested_mode=$mode"

    if [[ "$mode" == all ]]; then
        run_mode optimized
        run_mode debug
        run_mode sanitizer
    else
        run_mode "$mode"
    fi
}

# The subshell restores fail-fast behavior even while the parent captures status.
set +e
(set -e; run_qualification) 2>&1 | tee "$task_log"
qualification_statuses=("${PIPESTATUS[@]}")
qualification_status=${qualification_statuses[0]}
if [[ $qualification_status -eq 0 ]]; then
    qualification_status=${qualification_statuses[1]}
fi
set -e

mkdir -p "$(dirname "$output")"
cp "$task_log" "$output"
echo "qualification record: $output"
exit "$qualification_status"
