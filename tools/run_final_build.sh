#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
PROJECT="$(cd "$SCRIPT_DIR/.." && pwd)"
LOG="${BUILD_LOG:-$PROJECT/build_final_v561.log}"

cd "$PROJECT"
: "${KS_PASS:?Signing password was not provided to the build process}"
BM_SKIP_BACKUP=1 bash ./build_bmtts_v520_complete_cached.sh >"$LOG" 2>&1
