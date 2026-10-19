#!/usr/bin/env bash
# Download into the user's Downloads folder without overwriting existing work.
set -euo pipefail
DESTINATION="${AI_TE_103_DIRECTORY:-$HOME/Downloads/AI-TE-103}"
fail() { printf '\nInstallation stopped: %s\n' "$*" >&2; exit 1; }
case "$(uname -s)" in Linux|Darwin) ;; *) fail 'Use the PowerShell installer on Windows.' ;; esac
PARENT="$(dirname -- "$DESTINATION")"
mkdir -p -- "$PARENT"
PARENT="$(CDPATH= cd -- "$PARENT" && pwd -P)"
DESTINATION="$PARENT/$(basename -- "$DESTINATION")"
[ ! -L "$DESTINATION" ] || fail "The selected destination is a directory link: $DESTINATION"
STAGING=''
ARCHIVE=''
cleanup() {
    if [ -n "$ARCHIVE" ]; then rm -f -- "$ARCHIVE"; fi
    if [ -n "$STAGING" ]; then
        # mktemp created this exact new directory under the resolved parent.
        # Never remove the final destination or an existing project.
        case "$STAGING" in
            "$PARENT"/.AI-TE-103-download.*) rm -rf -- "$STAGING" ;;
            *) printf 'Keeping unexpected staging path: %s\n' "$STAGING" >&2 ;;
        esac
    fi
}
trap cleanup EXIT
complete_project() {
    local name
    for name in app.py run.sh tools/start_unix.py requirements.txt requirements-dev.txt constraints.txt expert_system/__init__.py search_algorithm/__init__.py fuzzy_logic/__init__.py multi_agent_system/__init__.py interface/fleet_session.py; do
        [ -f "$1/$name" ] || return 1
    done
}
if [ -e "$DESTINATION" ]; then
    [ -d "$DESTINATION" ] && complete_project "$DESTINATION" || fail "The destination already exists but is not a complete current project: $DESTINATION. Nothing was overwritten. Update it or choose another location."
    printf 'Using the existing project at %s\nYour files are preserved; this installer does not pull or overwrite them.\n' "$DESTINATION"
else
    STAGING="$(mktemp -d "$PARENT/.AI-TE-103-download.XXXXXX")"
    GIT="$(command -v git || true)"
    if [ "$(uname -s)" = Darwin ] && [ "$GIT" = /usr/bin/git ] && ! xcode-select -p >/dev/null 2>&1; then
        # The Apple Git stub can otherwise open a Command Line Tools installer.
        GIT=''
    fi
    if [ -n "$GIT" ]; then
        printf 'Cloning AI-TE-103 into %s...\n' "$DESTINATION"
        "$GIT" clone https://github.com/sar1p/AI-TE-103.git "$STAGING" || fail 'Clone failed. Check the error above; running again will retry.'
    else
        printf 'Git was not found. Downloading the source archive into %s...\n' "$DESTINATION"
        ARCHIVE="$(mktemp "${TMPDIR:-/tmp}/AI-TE-103-source.XXXXXX")"
        URL='https://github.com/sar1p/AI-TE-103/archive/refs/heads/main.tar.gz'
        if command -v curl >/dev/null 2>&1; then
            curl --fail --location --silent --show-error "$URL" --output "$ARCHIVE" || fail 'Download failed. Check your internet connection and try again.'
        elif command -v wget >/dev/null 2>&1; then
            wget -q "$URL" -O "$ARCHIVE" || fail 'Download failed. Check your internet connection and try again.'
        else
            fail 'A download tool is missing. Install curl or wget using your operating system package manager.'
        fi
        tar -xzf "$ARCHIVE" -C "$STAGING" --strip-components=1 || fail 'The archive could not be extracted. Try downloading it again.'
    fi
    complete_project "$STAGING" || fail 'The project download is incomplete. Run the installer again.'
    [ ! -e "$DESTINATION" ] && [ ! -L "$DESTINATION" ] || fail 'Another process created the destination. Nothing was overwritten.'
    # Claim an empty final directory atomically. Never move a checkout into a
    # directory that a competing installer or user created between checks.
    mkdir -- "$DESTINATION" || fail 'Another process created the destination. Nothing was overwritten.'
    cp -R -p "$STAGING/." "$DESTINATION/" || fail 'Copy failed. The partial destination is preserved for inspection; choose another location to retry.'
    cleanup
    STAGING=''
    ARCHIVE=''
fi
bash "$DESTINATION/run.sh" "$@"
