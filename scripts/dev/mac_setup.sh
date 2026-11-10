#!/bin/sh
# (raiders) Mac development setup: the Python environment for nx2/ and the game-free tests, and liba64emit for the
# lifter. Safe to run again: a venv, a package or a library that is already there is left alone.
#
#     scripts/dev/mac_setup.sh                 # .venv with python3
#     PYTHON=python3.12 scripts/dev/mac_setup.sh   # (a fresh .venv with another Python: remove .venv first)
#
# Nothing here reads the game. Results: docs/plans/reports/mac-test-baseline.md.
set -eu

ROOT=$(cd "$(dirname "$0")/../.." && pwd)
cd "$ROOT"
PYTHON=${PYTHON:-python3}
VPY=.venv/bin/python
# (the pipeline's packages, as CONTRIBUTING.md and CLAUDE.md list them; the Unicorn pin is upstream's)
PACKAGES='lz4 numpy capstone unicorn>=2.1,<2.2 zstandard'

if [ "$(uname -s)" != Darwin ]; then
    echo "mac_setup.sh: for macOS; on Linux use scripts/linux/deps.sh" >&2
    exit 1
fi

if [ ! -x "$VPY" ]; then
    command -v "$PYTHON" >/dev/null || { echo "mac_setup.sh: $PYTHON not found (brew install python)" >&2; exit 1; }
    echo "creating .venv with $("$PYTHON" -V 2>&1)"
    "$PYTHON" -m venv .venv
fi

# (only what is missing is installed: pip leaves a satisfied requirement alone, so a second run changes nothing)
missing=$("$VPY" -I - $PACKAGES <<'PY'
import sys
from importlib import metadata
try:
    from packaging.requirements import Requirement
except ImportError:
    from pip._vendor.packaging.requirements import Requirement
for spec in sys.argv[1:]:
    r = Requirement(spec)
    try:
        ok = r.specifier.contains(metadata.version(r.name), prereleases=True)
    except metadata.PackageNotFoundError:
        ok = False
    if not ok:
        print(spec)
PY
)
if [ -n "$missing" ]; then
    echo "installing:" $missing
    # shellcheck disable=SC2086
    if ! "$VPY" -I -m pip install -q --disable-pip-version-check $missing; then
        echo "mac_setup.sh: pip could not install:" $missing >&2
        echo "  If it is unicorn (no wheel for $("$VPY" -V 2>&1) on $(uname -m)), keep the pin and use an older Python:" >&2
        echo "    brew install python@3.12 && rm -rf .venv && PYTHON=python3.12 scripts/dev/mac_setup.sh" >&2
        exit 1
    fi
fi

command -v clang++ >/dev/null || { echo "mac_setup.sh: clang++ not found (xcode-select --install)" >&2; exit 1; }

# (build_emit.py rebuilds only when a64emit.cpp or suyu/arm64_to_c.h changed: liba64emit.so.sha1 is its stamp)
"$VPY" -I third_party/a64-kit/lift/build_emit.py >/dev/null

echo "---- versions"
echo "macOS     $(sw_vers -productVersion) $(uname -m)"
echo "python    $("$VPY" -V 2>&1 | cut -d' ' -f2)  (.venv)"
"$VPY" -I - $PACKAGES <<'PY'
import re, sys
from importlib import metadata
for spec in sys.argv[1:]:
    name = re.split(r"[<>=!~]", spec)[0]
    print("%-9s %s" % (name, metadata.version(name)))
PY
echo "clang++   $(clang++ --version | head -1)"
echo "a64emit   third_party/a64-kit/lift/liba64emit.so (source sha1 $(cat third_party/a64-kit/lift/liba64emit.so.sha1))"
# (optional tools a few game-free checks use; run_all.py skips those checks without them)
for t in spirv-val glslangValidator; do
    printf '%-9s %s\n' "$t" "$(command -v "$t" || echo 'not found (brew install spirv-tools glslang)')"
done
if command -v brew >/dev/null && [ -f "$(brew --prefix)/include/vulkan/vulkan.h" ]; then
    echo "vulkan.h  $(brew --prefix)/include  (export HOOKSHOT_VULKAN_HEADERS=$(brew --prefix)/include)"
else
    echo "vulkan.h  not found (brew install vulkan-headers)"
fi
if command -v brew >/dev/null && [ -f "$(brew --prefix)/include/spirv/unified1/spirv.h" ]; then
    echo "spirv.h   $(brew --prefix)/include  (export HOOKSHOT_SPIRV_HEADERS=$(brew --prefix)/include)"
else
    echo "spirv.h   not found (brew install spirv-headers)"
fi
