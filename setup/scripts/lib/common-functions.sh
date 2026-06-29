# shellcheck shell=bash
# -----------------------------------------------------------------------------
# common-functions.sh
#
# Sourced by every phase script. Provides:
#   * Strict-mode setup, logging, ERR trap.
#   * Idempotency markers (a phase exits 0 if already complete).
#   * Codename detection (jammy / noble / ...).
#   * Apt helpers that don't fight cloud-init's unattended-upgrades.
#   * Small convenience helpers (have_cmd, on_path, etc.).
#
# Conventions:
#   * Working root is /opt/rt-stack (created on demand).
#   * Per-phase marker files live under /var/lib/rt-stack/markers/.
#   * Per-phase logs live under /var/log/rt-stack/.
#
# Source guard so multiple includes are harmless.
# -----------------------------------------------------------------------------
[[ -n "${__RT_COMMON_FUNCTIONS_SOURCED:-}" ]] && return 0
__RT_COMMON_FUNCTIONS_SOURCED=1

export DEBIAN_FRONTEND=noninteractive
export NEEDRESTART_MODE=a   # auto-restart services instead of prompting

RT_WORKDIR="${RT_WORKDIR:-/opt/rt-stack}"
RT_STATE_DIR="${RT_STATE_DIR:-/var/lib/rt-stack}"
RT_MARKER_DIR="${RT_STATE_DIR}/markers"
RT_LOG_DIR="${RT_LOG_DIR:-/var/log/rt-stack}"

mkdir -p "$RT_WORKDIR" "$RT_MARKER_DIR" "$RT_LOG_DIR"

# ----------------------------------------------------------------------------
# Strict mode + logging
# ----------------------------------------------------------------------------
rt_strict_mode() {
    set -Eeuo pipefail
    trap 'rt_err_trap $? $LINENO $BASH_LINENO "$BASH_COMMAND" $(printf "::%s" "${FUNCNAME[@]:-}")' ERR
}

rt_err_trap() {
    local exit_code=$1 line=$2
    local cmd=$4
    echo "[FATAL] exit=$exit_code line=$line cmd: $cmd" >&2
}

# Tee all stdout/stderr to a per-phase log file while still printing to console.
rt_setup_logging() {
    local phase="$1"
    local log="${RT_LOG_DIR}/${phase}.log"
    # If we are already redirected (e.g. by cloud-init), don't double-tee.
    if [[ -z "${__RT_LOGGING_FOR:-}" ]]; then
        exec > >(tee -a "$log") 2>&1
        export __RT_LOGGING_FOR="$phase"
    fi
    echo "===== $(date -u +%FT%TZ) :: phase=$phase :: starting ====="
}

# ----------------------------------------------------------------------------
# Idempotency markers
# ----------------------------------------------------------------------------
rt_marker_for() { echo "${RT_MARKER_DIR}/${1}.done"; }

rt_already_done() {
    local phase="$1"
    [[ -f "$(rt_marker_for "$phase")" ]]
}

rt_mark_done() {
    local phase="$1"
    date -u +%FT%TZ > "$(rt_marker_for "$phase")"
    echo "===== $(date -u +%FT%TZ) :: phase=$phase :: complete ====="
}

# Skip the rest of the calling script if the phase is already complete.
rt_skip_if_done() {
    local phase="$1"
    if rt_already_done "$phase"; then
        echo "[skip] phase=$phase already complete (marker: $(rt_marker_for "$phase"))"
        exit 0
    fi
}

# ----------------------------------------------------------------------------
# OS / codename detection
# ----------------------------------------------------------------------------
rt_codename() {
    # Prefer UBUNTU_CODENAME, fall back to VERSION_CODENAME, then lsb_release.
    . /etc/os-release 2>/dev/null || true
    echo "${UBUNTU_CODENAME:-${VERSION_CODENAME:-$(lsb_release -cs 2>/dev/null || echo unknown)}}"
}

rt_arch() { dpkg --print-architecture; }

# ----------------------------------------------------------------------------
# Apt helpers
# ----------------------------------------------------------------------------
rt_wait_apt() {
    # Cloud-init may still be running apt in the background; wait it out.
    local i=0
    while sudo fuser /var/lib/dpkg/lock-frontend >/dev/null 2>&1 \
       || sudo fuser /var/lib/apt/lists/lock >/dev/null 2>&1 \
       || sudo fuser /var/lib/dpkg/lock         >/dev/null 2>&1; do
        ((i++)) || true
        if (( i % 12 == 1 )); then
            echo "[apt] waiting for another package manager to finish..."
        fi
        sleep 5
        if (( i > 180 )); then
            echo "[apt] still locked after 15min; giving up" >&2
            return 1
        fi
    done
}

rt_apt_update() { rt_wait_apt; apt-get update -y; }

rt_apt_install() {
    rt_wait_apt
    apt-get install -y --no-install-recommends "$@"
}

# ----------------------------------------------------------------------------
# Misc
# ----------------------------------------------------------------------------
have_cmd() { command -v "$1" >/dev/null 2>&1; }

# Lazy clone: only clone if dir is missing.
rt_git_clone() {
    local url="$1" dir="$2" branch="${3:-}"
    if [[ -d "$dir/.git" ]]; then
        echo "[git] $dir already cloned, skipping"
        return 0
    fi
    if [[ -n "$branch" ]]; then
        git clone --depth 1 -b "$branch" "$url" "$dir"
    else
        git clone --depth 1 "$url" "$dir"
    fi
}

# Run a command and echo it first (transparency in logs).
rt_run() { echo "+ $*"; "$@"; }
