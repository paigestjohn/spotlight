#!/usr/bin/env bash
# Build and smoke-test the pinned Spotlight sandbox image without API spend.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
IMAGE="${SPOTLIGHT_SANDBOX_IMAGE:-spotlight-sandbox:local}"

cd "$ROOT"

for secret in .env .env.local .env.production secrets.txt credentials.txt; do
  if [ -e "$secret" ]; then
    echo "Refusing to build with secret-like file in context: $secret" >&2
    exit 2
  fi
done

if ! command -v docker >/dev/null 2>&1; then
  echo "docker not found; install Docker or run this inside an environment with Docker access" >&2
  exit 2
fi

if ! grep -Eq '^FROM node:[^[:space:]]+@sha256:[a-f0-9]{64}$' container/Dockerfile; then
  echo "Dockerfile base image must be pinned by digest" >&2
  exit 2
fi

if grep -Ev '^[[:space:]]*(#|$|[a-z0-9.+-]+=([0-9][A-Za-z0-9:.+~_-]*))$' container/apt-packages.txt | grep -q .; then
  echo "container/apt-packages.txt must contain exact package=version pins only" >&2
  exit 2
fi

python3 - <<'PY'
import json
import pathlib
import sys

pkg = json.loads(pathlib.Path("container/package.json").read_text())
lock = json.loads(pathlib.Path("container/package-lock.json").read_text())
deps = pkg.get("dependencies", {})
lock_deps = lock.get("packages", {}).get("", {}).get("dependencies", {})
if deps != lock_deps:
    print("container/package-lock.json root dependencies do not match package.json", file=sys.stderr)
    sys.exit(2)
for name, version in deps.items():
    if not isinstance(version, str) or version.startswith(("^", "~", ">", "<", "*")):
        print(f"npm dependency {name} is not exactly pinned: {version!r}", file=sys.stderr)
        sys.exit(2)
PY

docker build -f container/Dockerfile -t "$IMAGE" .

manifest_tmp="$(mktemp)"
docker run --rm "$IMAGE" bash -lc "dpkg-query -W -f='\${binary:Package}=\${Version}\n' | sort" > "$manifest_tmp"
if ! diff -u container/dpkg-manifest.txt "$manifest_tmp"; then
  rm -f "$manifest_tmp"
  echo "Installed Debian package manifest drifted from container/dpkg-manifest.txt" >&2
  exit 2
fi
rm -f "$manifest_tmp"

docker run --rm "$IMAGE" bash -c 'python3 --version && node --version && npm --version && firecrawl --version && qmd --version'
docker run --rm -v "$ROOT:/host-workspace:ro" "$IMAGE" bash -c 'cp -a /host-workspace/. /tmp/spotlight-workspace && cd /tmp/spotlight-workspace && bash tests/smoke.sh'
