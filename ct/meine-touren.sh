#!/usr/bin/env bash
# Proxmox-Helper-Script (Stil und Engine: community-scripts). Läuft auf dem Proxmox-VE-Host.
# Das Skript stammt aus diesem Repository; die Container-Engine (build.func) wird von community-scripts geladen,
# der Installer (install/meine-touren-install.sh) aus diesem Repository.
#
#   bash -c "$(curl -fsSL https://raw.githubusercontent.com/hilde0407/meine-touren/main/ct/meine-touren.sh)"
#
export COMMUNITY_SCRIPTS_URL="${COMMUNITY_SCRIPTS_URL:-https://raw.githubusercontent.com/hilde0407/meine-touren/main}"
export REPO_SLUG="${REPO_SLUG:-hilde0407/meine-touren}"
source <(curl -fsSL "${COMMUNITY_SCRIPTS_CORE_URL:-https://raw.githubusercontent.com/community-scripts/core/main}/core/build.func")
# Copyright (c) 2026 hilde0407
# License: MIT | https://github.com/hilde0407/meine-touren/raw/main/LICENSE
# Source: https://github.com/hilde0407/meine-touren

APP="Meine-Touren"
var_tags="${var_tags:-touren;wandern;gps}"
var_cpu="${var_cpu:-2}"
var_ram="${var_ram:-2048}"
var_disk="${var_disk:-20}"
var_os="${var_os:-debian}"
var_version="${var_version:-13}"
var_unprivileged="${var_unprivileged:-1}"

header_info "$APP"
variables
color
catch_errors

function update_script() {
  header_info
  check_container_storage
  check_container_resources
  if [[ ! -d /opt/meine-touren && ! -d /opt/komoot-hub ]]; then
    msg_error "No ${APP} Installation Found!"
    exit
  fi

  if check_for_gh_release "meine-touren" "hilde0407/meine-touren"; then
    msg_info "Updating ${APP} (a backup is created first)"
    CLEAN_INSTALL=1 fetch_and_deploy_gh_release "meine-touren" "hilde0407/meine-touren" "tarball" "latest" "/opt/meine-touren-src"
    if [[ -x /usr/local/bin/meine-touren-update ]]; then
      $STD /usr/local/bin/meine-touren-update /opt/meine-touren-src
    else
      $STD bash /opt/meine-touren-src/deploy/install.sh
    fi
    msg_ok "Updated ${APP}"
  fi
  exit
}

start
build_container
description

msg_ok "Completed successfully!\n"
echo -e "${CREATING}${GN}${APP} setup has been successfully initialized!${CL}"
echo -e "${INFO}${YW}Open it in your browser (the first visit creates the administrator account):${CL}"
echo -e "${GATEWAY}${BGN}http://${IP}${CL}"
