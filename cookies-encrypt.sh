#!/usr/bin/env bash
set -euo pipefail

INPUT_FILE="${1:-cookies.json}"
OUTPUT_FILE="${2:-cookies.json.asc}"
RECIPIENT="${3:-${GPG_RECIPIENT:-${GPG_RECIPIENT_EMAIL:-}}}"

exec "gpg-encrypt.sh" "$INPUT_FILE" "$OUTPUT_FILE" "$RECIPIENT"
