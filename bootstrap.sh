#!/usr/bin/env bash
set -euo pipefail
ROOT=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
export PYTHONDONTWRITEBYTECODE=1

# The default is a read-only plan. Privilege is never requested in this wrapper.
if ! command -v python3 >/dev/null 2>&1; then
    printf '%s\n' 'Python 3 é pré-requisito. Instale python no destino antes de continuar.' >&2
    exit 2
fi
exec python3 "$ROOT/scripts/setup.py" "$@"
