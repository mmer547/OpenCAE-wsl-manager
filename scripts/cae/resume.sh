#!/bin/bash
set -euo pipefail
cd /root
mkdir -p wsl-manager-completed
run_step() {
    local script=$1
    if [[ ! -f "wsl-manager-completed/$script" ]]; then
        echo "Installing: $script"
        bash "./$script"
        touch "wsl-manager-completed/$script"
    fi
}
if [[ $# -eq 1 ]]; then
    run_step "$1"
else
    while IFS= read -r script; do
        run_step "$script" </dev/null
    done < wsl-manager-plan
fi
