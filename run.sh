#!/usr/bin/env bash
# Bash 3.2-compatible bootstrap for Linux and macOS. No global installation.
set -euo pipefail
ROOT="$(CDPATH= cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)"
cd -- "$ROOT"
RUNTIME="$ROOT/.runtime"
MANAGED=0
for argument in "$@"; do
    case "$argument" in
        --managed-python) MANAGED=1 ;;
        --help|-h)
            printf '%s\n' 'Usage: bash run.sh [--setup-only] [--verify] [--no-browser] [--port NUMBER] [--managed-python]'
            exit 0 ;;
    esac
done
fail() { printf '\nSetup stopped: %s\n' "$*" >&2; exit 1; }
for name in app.py requirements.txt requirements-dev.txt constraints.txt tools/start_unix.py; do
    [ -f "$ROOT/$name" ] || fail "The project is incomplete (missing $name). Extract the whole archive first."
done
for path in "$RUNTIME" "$ROOT/.venv"; do
    [ ! -L "$path" ] || fail "Use a normal project folder; this setup path is a directory link: $path"
    [ ! -e "$path" ] || [ -d "$path" ] || fail "This setup path is a file: $path"
done
case "$(uname -s):$(uname -m)" in
    Linux:x86_64) TARGET=x86_64-unknown-linux-gnu; HASH=1468ebd5a5541121837c5a2817b9972ba6090fa6caa3d142620850a47fb75154 ;;
    Linux:aarch64|Linux:arm64) TARGET=aarch64-unknown-linux-gnu; HASH=3ccfb6af6e242433eb552f7d9676abd5412c6595c497e990d9c8cb7b5bd4d2c3 ;;
    Darwin:x86_64) TARGET=x86_64-apple-darwin; HASH=5f44dcbde809b632f47c36fadb241cb4d6f9af71d0c8f172b5d2026d3dde742c ;;
    Darwin:arm64) TARGET=aarch64-apple-darwin; HASH=a9c1b29002cf3c83f07fa9cd8a887a3be0107d90e23189721221e7257db8e3d6 ;;
    *) fail 'This launcher supports Linux/macOS on x86_64 or ARM64. On Windows use run.bat.' ;;
esac
if [ "$(uname -s)" = Linux ] && command -v ldd >/dev/null 2>&1; then
    LDD_VERSION="$(ldd --version 2>&1 || true)"
    if printf '%s\n' "$LDD_VERSION" | grep -qi musl; then
        fail 'These pinned packages require a glibc Linux distribution. Alpine/musl is not supported.'
    fi
fi
printf '\nAI-TE-303 | Warehouse Operations\nProject folder: %s\n[1/3] Preparing Python 3.12...\n' "$ROOT"
ENV_PYTHON="$ROOT/.venv/bin/python"
valid_environment() {
    [ -f "$ROOT/.venv/pyvenv.cfg" ] && [ -x "$ENV_PYTHON" ] &&
        "$ENV_PYTHON" -c 'import os,sys,pip; sys.exit(0 if sys.version_info[:2]==(3,12) and sys.maxsize>2**32 and sys.prefix!=sys.base_prefix and os.path.realpath(sys.prefix)==os.path.realpath(sys.argv[1]) else 1)' "$ROOT/.venv" >/dev/null 2>&1
}
download() {
    if command -v curl >/dev/null 2>&1; then
        curl --fail --location --silent --show-error "$1" --output "$2"
    elif command -v wget >/dev/null 2>&1; then
        wget -q "$1" -O "$2"
    else
        fail 'A download tool is missing. Install curl or wget using your operating system package manager.'
    fi
}
checksum() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    elif command -v shasum >/dev/null 2>&1; then
        shasum -a 256 "$1" | awk '{print $1}'
    else
        fail 'A SHA256 tool is missing. This launcher needs sha256sum or shasum.'
    fi
}
UV=''
BASE="$ENV_PYTHON"
if ! valid_environment; then
    VERSION=0.13.0
    UV_FOLDER="$RUNTIME/uv-$VERSION-$TARGET"
    UV="$UV_FOLDER/uv"
    for path in "$UV_FOLDER" "$RUNTIME/python" "$RUNTIME/cache"; do
        [ ! -L "$path" ] || fail "Use a normal runtime folder: $path"
    done
    mkdir -p -- "$RUNTIME"
    UV_READY=0
    if [ -x "$UV" ]; then
        case "$("$UV" --version 2>/dev/null || true)" in "uv $VERSION"|"uv $VERSION "*) UV_READY=1 ;; esac
    fi
    if [ "$UV_READY" = 0 ]; then
        STAGING="$(mktemp -d "$RUNTIME/uv-download.XXXXXX")"
        ARCHIVE="$STAGING/download.tar.gz"
        trap 'rm -f -- "$STAGING/download.tar.gz" "$STAGING/uv"; rmdir -- "$STAGING" 2>/dev/null || true' EXIT
        printf '%s\n' 'Downloading the project-local setup tool...'
        download "https://github.com/astral-sh/uv/releases/download/$VERSION/uv-$TARGET.tar.gz" "$ARCHIVE" || fail 'Download failed. Check your internet connection, then run again.'
        [ "$(checksum "$ARCHIVE")" = "$HASH" ] || fail 'The setup-tool download has an unexpected checksum. Run again to retry.'
        # A hard link publishes a complete verified file atomically. Concurrent
        # starters cannot extract over an executable that another one is using.
        mkdir -p -- "$UV_FOLDER"
        tar -xzf "$ARCHIVE" -C "$STAGING" --strip-components=1 "uv-$TARGET/uv" || fail 'Could not extract the setup tool.'
        chmod u+x "$STAGING/uv"
        if ! ln -- "$STAGING/uv" "$UV" 2>/dev/null; then
            case "$("$UV" --version 2>/dev/null || true)" in
                "uv $VERSION"|"uv $VERSION "*) ;;
                *) fail "The setup-tool cache is invalid. Keep this folder for inspection: $UV_FOLDER" ;;
            esac
        fi
        rm -f -- "$STAGING/download.tar.gz" "$STAGING/uv"
        rmdir -- "$STAGING"
        trap - EXIT
    fi
    export UV_PYTHON_INSTALL_DIR="$RUNTIME/python" UV_CACHE_DIR="$RUNTIME/cache"
    export UV_PYTHON_INSTALL_BIN=0 UV_NO_CONFIG=1 UV_NO_PROGRESS=1
    BASE=''
    if [ "$MANAGED" = 0 ] && command -v python3.12 >/dev/null 2>&1; then
        BASE="$(python3.12 -c 'import sys; sys.exit(1) if sys.version_info[:2]!=(3,12) or sys.maxsize<=2**32 else print(sys.executable)' 2>/dev/null || true)"
    fi
    if [ -z "$BASE" ]; then
        printf '%s\n' 'Preparing a private Python 3.12 runtime. First setup needs internet...'
        "$UV" python install --no-bin --install-dir "$RUNTIME/python" 3.12 || fail 'Python download failed. Check the error above and run again.'
        BASE="$("$UV" python find --managed-python --no-python-downloads 3.12)" || fail 'The private Python runtime could not be found.'
    fi
fi
# Python uses a kernel file lock before creating or changing .venv. The lock
# releases on process death; no stale PID file or directory recovery is needed.
exec "$BASE" "$ROOT/tools/start_unix.py" --uv "$UV" --base-python "$BASE" "$@"
