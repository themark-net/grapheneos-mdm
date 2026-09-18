#!/usr/bin/env bash
# Local CI mirror for issue #3 (run before push).
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

echo "== protocol schema tests =="
python3 -m unittest discover -s protocol/tests -v

echo "== lab check-in mTLS tests =="
python3 -m unittest discover -s server/tests -v

if [ -x ./gradlew ]; then
  echo "== gradle unit tests =="
  ./gradlew --no-daemon test
elif command -v gradle >/dev/null 2>&1; then
  echo "== gradle wrapper + unit tests =="
  gradle wrapper --gradle-version 8.9
  ./gradlew --no-daemon test
else
  echo "SKIP gradle unit tests (no gradlew/gradle; GHA will run them)"
fi

echo "ci-local OK"
