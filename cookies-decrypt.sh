#!/usr/bin/env bash
set -euo pipefail

INPUT_FILE="${1:-cookies.json.asc}"
OUTPUT_FILE="${2:-cookies.json}"

exec "gpg-decrypt.sh" "$INPUT_FILE" "$OUTPUT_FILE"
