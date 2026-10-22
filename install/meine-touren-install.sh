#!/usr/bin/env bash

# Copyright (c) 2026 hilde0407
# License: MIT | https://github.com/hilde0407/meine-touren/raw/main/LICENSE
# Source: https://github.com/hilde0407/meine-touren

source /dev/stdin <<<"$FUNCTIONS_FILE_PATH"
color
verb_ip6
catch_errors
setting_up_container
network_check
update_os

fetch_and_deploy_gh_release "meine-touren" "hilde0407/meine-touren" "tarball" "latest" "/opt/meine-touren-src"

msg_info "Installing Meine Touren (Python, nginx, systemd service, daily backup)"
$STD bash /opt/meine-touren-src/deploy/install.sh
msg_ok "Installed Meine Touren"

motd_ssh
customize
cleanup_lxc
