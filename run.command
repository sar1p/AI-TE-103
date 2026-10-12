#!/usr/bin/env bash
# Terminal entry point for a macOS clone; ZIP permissions can vary by extractor.
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
bash "$ROOT/run.sh" "$@"
result=$?
if [ "$result" -ne 0 ] && [ -t 0 ]; then
    printf '\nPlease read the message above. Press Enter to close this window.\n'
    read -r answer
fi
exit "$result"
