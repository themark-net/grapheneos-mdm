#!/usr/bin/env bash
# Certificate and key files that must not sit under the uploaded CI log dir.
# Sourced by scripts/ci-emulator-policy.sh.
#
# *.bks is the BouncyCastle keystore suffix. The workflow exclusion for the
# same suffix is the line `!/tmp/mdm-ci/**/*.bks` in
# .github/workflows/emulator-policy.yml (artifact emulator-policy-logs).

# Print matching file paths, then any directory named certs. Empty when clean.
cert_guard_hits() {
  local root="$1"
  find "$root" -type f \( \
    -name '*.pem' -o -name '*.p12' -o -name '*.key' -o -name '*.crt' \
    -o -name '*.der' -o -name '*.cer' -o -name '*.pfx' \
    -o -name '*.jks' -o -name '*.keystore' -o -name '*.csr' \
    -o -name '*.bks' \
  \) -print 2>/dev/null || true
  find "$root" -type d -name certs -print 2>/dev/null || true
}
