#!/bin/bash
# Installs or updates Radio LoLa on a Reachy Mini Wireless.
# Run on the robot (after "ssh pollen@reachy-mini.local"):
#   curl -fsSL https://github.com/Moe-Joe86/Radio-LoLa/releases/latest/download/install.sh | bash
#
# Follows Pollen's documentation ("Offline / manual deployment for a Wireless unit"): apps live in /venvs/apps_venv.
# The package is installed without dependencies because reachy-mini (with numpy and GStreamer) is already there.
# The station list on the robot (~/.config/radio_lola/stations.json) is not touched.
set -euo pipefail

# These three values can only be changed for testing.
PACKAGE="${RADIO_PACKAGE:-https://github.com/Moe-Joe86/Radio-LoLa/releases/latest/download/radio_lola-1.0.0-py3-none-any.whl}"
APPS="${RADIO_APPS:-/venvs/apps_venv}"
DAEMON="${RADIO_DAEMON:-/venvs/mini_daemon}"

install_into() {  # install_into <python> <package…>
    local python="$1"; shift
    if command -v uv >/dev/null 2>&1; then
        uv pip install --python "$python" "$@"
    elif [ -x /opt/uv/uv ]; then
        /opt/uv/uv pip install --python "$python" "$@"
    else
        "$python" -m pip install "$@"
    fi
}

if [ ! -x "$APPS/bin/python" ]; then
    # This is also how the daemon creates the app environment when the first app is installed from the app store.
    echo "Radio LoLa: creating the app environment $APPS …"
    "$DAEMON/bin/python" -m venv "$APPS"
    VERSION=$("$DAEMON/bin/python" -c "from importlib.metadata import version; print(version('reachy_mini'))")
    install_into "$APPS/bin/python" "reachy-mini==$VERSION"
fi

echo "Radio LoLa: downloading and installing the app …"
install_into "$APPS/bin/python" --no-deps --force-reinstall "$PACKAGE"

"$APPS/bin/python" -c "from radio_lola.main import RadioLola; from radio_lola.settings import load; load()"
LIST=$(curl -fsS http://localhost:8000/api/apps/list-available/installed || true)
if grep -q '"radio_lola"' <<<"$LIST"; then
    echo "Radio LoLa: DONE. The daemon knows the app. Now press “Start radio” in the phone app."
else
    echo "Radio LoLa: installed, but the daemon does not list it yet. Switch the robot off and on once."
fi
