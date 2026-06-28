#!/bin/bash
#
# MMU KlipperScreen Happy Hare edition supplemental installer
#
# Copyright (C) 2023-2025  moggieuk#6538 (discord)
#                          moggieuk@hotmail.com
#
# Screen Capture: scrot -s -D :0.0
#
SCRIPT="$(readlink -f "$0")"
SCRIPTFILE="$(basename "$SCRIPT")"
SCRIPTPATH="$(dirname "$SCRIPT")"
SCRIPTNAME="$0"
ARGS=( "$@" )

KLIPPERSCREEN_DIR="${HOME}/KlipperScreen"
KLIPPER_CONFIG_HOME="${HOME}/printer_data/config"
OLD_KLIPPER_CONFIG_HOME="${HOME}/klipper_config"

OS_FLYOS_FAST="flyos-fast"
OS_TYPE=""
if [ "$(sed -n 's/^NAME="\(.*\)"/\1/p' /etc/os-release 2>/dev/null)" = "FlyOS-Fast" ]; then
    OS_TYPE="${OS_FLYOS_FAST}"
    echo "Detected FlyOS-Fast"
fi

if [ "$OS_TYPE" = "$OS_FLYOS_FAST" ]; then
    KLIPPERSCREEN_DIR="/data/KlipperScreen"
    KLIPPER_CONFIG_HOME="/usr/share/printer_data/config"
    OLD_KLIPPER_CONFIG_HOME="/data/klipper_config"
fi

set -e # Exit immediately on error

declare -A PIN 2>/dev/null || {
    echo "Please run this script with ./bash $0"
    exit 1
}

# Screen Colors
OFF='\033[0m'             # Text Reset
BLACK='\033[0;30m'        # Black
RED='\033[0;31m'          # Red
GREEN='\033[0;32m'        # Green
YELLOW='\033[0;33m'       # Yellow
BLUE='\033[0;34m'         # Blue
PURPLE='\033[0;35m'       # Purple
CYAN='\033[0;36m'         # Cyan
WHITE='\033[0;37m'        # White

B_RED='\033[1;31m'        # Bold Red
B_GREEN='\033[1;32m'      # Bold Green
B_YELLOW='\033[1;33m'     # Bold Yellow
B_CYAN='\033[1;36m'       # Bold Cyan

INFO="${CYAN}"
EMPHASIZE="${B_CYAN}"
ERROR="${B_RED}"
WARNING="${B_YELLOW}"
PROMPT="${CYAN}"
INPUT="${OFF}"

self_update() {
    [ "$UPDATE_GUARD" ] && return
    export UPDATE_GUARD=YES
    clear

    cd "$SCRIPTPATH"

    set +e
    BRANCH=$(timeout 3s git branch --show-current)
    if [ $? -ne 0 ]; then
        echo -e "${ERROR}Error updating from github"
        echo -e "${ERROR}You might have an old version of git"
        echo -e "${ERROR}Skipping automatic update..."
        set -e
        return
    fi
    set -e

    [ -z "${BRANCH}" ] && {
        echo -e "${ERROR}Timeout talking to github. Skipping upgrade check"
        return
    }
    echo -e "${B_GREEN}Running on '${BRANCH}' branch"

    # Both check for updates but also help me not loose changes accidently
    echo -e "${B_GREEN}Checking for updates..."
    git fetch --quiet

    set +e
    git diff --quiet --exit-code "origin/$BRANCH"
    if [ $? -eq 1 ]; then
        echo -e "${B_GREEN}Found a new version of KlipperScreen - Happy Hare on github, updating..."
        [ -n "$(git status --porcelain)" ] && {
            git stash push -m 'local changes stashed before self update' --quiet
        }
        RESTART=1
    fi
    set -e

    if [ -n "${N_BRANCH}" -a "${BRANCH}" != "${N_BRANCH}" ]; then
        BRANCH=${N_BRANCH}
        echo -e "${B_GREEN}Switching to '${BRANCH}' branch"
        RESTART=1
    fi
    if [ -n "${RESTART}" ]; then
        git checkout $BRANCH --quiet
        git pull --quiet --force
        GIT_VER=$(git describe --tags)
        echo -e "${B_GREEN}Now on git version ${GIT_VER}"
        echo -e "${B_GREEN}Running the new install script..."
        cd - >/dev/null
        exec "$SCRIPTNAME" "${ARGS[@]}"
        exit 0 # Exit this old instance
    fi
    GIT_VER=$(git describe --tags)
    echo -e "${B_GREEN}Already the latest version: ${GIT_VER}"
}


function nextsuffix {
    local name="$1"
    local -i num=0
    while [ -e "$name.0$num" ]; do
        num+=1
    done
    printf "%s.0%d" "$name" "$num"
}


verify_not_root() {
    if [ "$OS_TYPE" = "$OS_FLYOS_FAST" ]; then
        echo -e "${WARNING}This script is run on a ${OS_TYPE} system, so we want it to be run as root"
        return
    fi
    if [ "$EUID" -eq 0 ]; then
        echo -e "${ERROR}This script must not run as root"
        exit -1
    fi
}


check_klipper() {
    if [ "$(sudo systemctl list-units --full -all -t service --no-legend | grep -F "klipper.service")" ]; then
        echo -e "${INFO}Klipper service found"
    else
        echo -e "${ERROR}Klipper service not found! Please install Klipper first"
        exit -1
    fi

}


verify_home_dirs() {
    if [ ! -d "${KLIPPER_CONFIG_HOME}" ]; then
        if [ ! -d "${OLD_KLIPPER_CONFIG_HOME}" ]; then
            echo -e "${ERROR}Klipper config directory (${KLIPPER_CONFIG_HOME} or ${OLD_KLIPPER_CONFIG_HOME}) not found. Use '-c <dir>' option to override"
            exit -1
        fi
        KLIPPER_CONFIG_HOME="${OLD_KLIPPER_CONFIG_HOME}"
    fi
    echo -e "${INFO}Klipper config directory (${KLIPPER_CONFIG_HOME}) found"
}


install_klipper_screen() {
    echo -e "${INFO}Adding KlipperScreen support for MMU"
    do_install=0
    ks_config="${KLIPPER_CONFIG_HOME}/KlipperScreen.conf"
    hh_config="${KLIPPER_CONFIG_HOME}/mmu_klipperscreen.conf"

    # Backup old Klippersreen Happy Hare menus
    if [ -f "${hh_config}" ]; then
        next_hh_config="$(nextsuffix "$hh_config")"
        echo -e "${WARNING}Pre upgrade config file moved to ${next_hh_config} for reference"
        mv ${hh_config} ${next_hh_config}
    fi

    # Ensure KlipperScreen.conf includes Happy Hare menus
    cat << EOF > /tmp/KlipperScreen.conf.tmp
# 
# MMU "Happy Hare edition" menus
#
[include mmu_klipperscreen.conf]

EOF

    if [ -f "${ks_config}" ]; then
        update_section=$(grep -c '\[include mmu_klipperscreen.conf\]' ${ks_config} || true)
        if [ "${update_section}" -eq 0 ]; then
            cat ${ks_config} >> /tmp/KlipperScreen.conf.tmp && cp /tmp/KlipperScreen.conf.tmp ${ks_config}
        else
            echo -e "${INFO}KlipperScreen MMU include already exists in conf. Skipping install"
        fi
    else
        cp /tmp/KlipperScreen.conf.tmp ${ks_config}
    fi

    echo -e "${INFO}Installing Happy Hare menus..."
    max_gate=$(expr $num_gates - 1)
    cp ${SRCDIR}/menus.conf "${hh_config}"

    for file in `ls ${SRCDIR}/iter*.conf`; do
        token=`basename $file .conf`
        echo -e "    ${INFO}Expanding menu ${token} for ${num_gates} gates"
	expanded=$(for i in $(eval echo "{0..`expr $num_gates - 1`}"); do
            cat ${SRCDIR}/${token}.conf | sed -e "s/{i}/${i}/g"
        done)
        expanded="# Generated menus for each tool/gate...\n${expanded}"
        awk -v r="$expanded" "{gsub(/^MMU_${token}/,r)}1" "${hh_config}" > /tmp/mmu_klipperscreen.conf.tmp && mv /tmp/mmu_klipperscreen.conf.tmp "${hh_config}"
    done

    # Always ensure images are linked for every style
    for style in `ls -d ${KLIPPERSCREEN_DIR}/styles/*/images`; do
        for img in `ls ${SRCDIR}/images`; do
            ln -sf "${SRCDIR}/images/${img}" "${style}/${img}"
        done
    done

    restart_klipperscreen
}


install_jetbrains_fonts() {
    local FORCE="${1:-}"

    echo -e "${INFO}Checking for JetBrains Mono..."

    if [ "$FORCE" != "--force" ] &&
       command -v fc-match >/dev/null 2>&1 &&
       fc-match "JetBrains Mono" 2>/dev/null | grep -q "JetBrainsMono"; then
        echo -e "${INFO}JetBrains Mono is already installed."
        return 0
    fi

    [ "$FORCE" = "--force" ] && \
        echo -e "${WARNING}Forcing JetBrains Mono reinstallation..."

    local FONT_NAME="JetBrainsMono"
    local ZIP_URL="https://download.jetbrains.com/fonts/JetBrainsMono-2.304.zip"
    local FONT_DIR
    local TMP_DIR

    if [ "$(id -u)" -eq 0 ]; then
        FONT_DIR="/usr/local/share/fonts/jetbrains-mono"
    else
        FONT_DIR="${HOME}/.local/share/fonts/jetbrains-mono"
    fi

    mkdir -p "$FONT_DIR"

    TMP_DIR="$(mktemp -d)" || {
        echo -e "${ERROR}Failed to create temporary directory."
        return 1
    }

    trap 'rm -rf "$TMP_DIR"' RETURN

    echo -e "${INFO}Downloading JetBrains Mono..."

    if command -v curl >/dev/null 2>&1; then
        if ! curl -fsSL "$ZIP_URL" -o "$TMP_DIR/$FONT_NAME.zip"; then
            echo -e "${ERROR}Failed to download JetBrains Mono."
            return 1
        fi
    elif command -v wget >/dev/null 2>&1; then
        if ! wget -q -O "$TMP_DIR/$FONT_NAME.zip" "$ZIP_URL"; then
            echo -e "${ERROR}Failed to download JetBrains Mono."
            return 1
        fi
    else
        echo -e "${ERROR}Neither curl nor wget is installed."
        return 1
    fi

    echo -e "${INFO}Extracting fonts..."

    if ! unzip -q "$TMP_DIR/$FONT_NAME.zip" -d "$TMP_DIR"; then
        echo -e "${ERROR}Failed to extract JetBrains Mono archive."
        return 1
    fi

    echo -e "${INFO}Installing fonts..."

    if ! find "$TMP_DIR" -type f \( -iname "*.ttf" -o -iname "*.otf" \) \
        -exec cp {} "$FONT_DIR/" \;; then
        echo -e "${ERROR}Failed to install font files."
        return 1
    fi

    echo -e "${INFO}Refreshing font cache..."

    if command -v fc-cache >/dev/null 2>&1; then
        fc-cache -f "$FONT_DIR"
    else
        echo -e "${WARNING}fc-cache not found. Font cache was not refreshed."
    fi

    echo -e "${INFO}JetBrains Mono installed successfully."
    return 0
}


install_update_manager() {
    echo -e "${INFO}Adding update manager to moonraker.conf"
    echo "${KLIPPER_CONFIG_HOME}/moonraker.conf"
    HH_GIT='origin: https://github.com/moggieuk/KlipperScreen-Happy-Hare-Edition.git'
    O1_GIT='origin: https://github.com/jordanruthe/KlipperScreen.git'
    O2_GIT='origin: https://github.com/KlipperScreen/KlipperScreen.git'

    if [ -f "${KLIPPER_CONFIG_HOME}/moonraker.conf" ]; then
        orig_section=$(egrep -c '^\[update_manager KlipperScreen\]' \
            ${KLIPPER_CONFIG_HOME}/moonraker.conf || true)
        hh_section=$(egrep -c '^\[update_manager KlipperScreen-happy_hare\]' \
            ${KLIPPER_CONFIG_HOME}/moonraker.conf || true)
        orig_origin1=$(egrep -c "^${O1_GIT}" ${KLIPPER_CONFIG_HOME}/moonraker.conf || true)
        orig_origin2=$(egrep -c "^${O2_GIT}" ${KLIPPER_CONFIG_HOME}/moonraker.conf || true)
        hh_origin2=$(egrep -c "^${HH_GIT}" ${KLIPPER_CONFIG_HOME}/moonraker.conf || true)

        if [ "${orig_section}" -ne 0 -a "${orig_origin1}" -ne 0 ]; then
            echo -e "${WARNING}Original [update_manager KlipperScreen] updated github origin to Happy Hare fork"
            cat ${KLIPPER_CONFIG_HOME}/moonraker.conf | sed -e "s%^${O1_GIT}%${HH_GIT}%" \
                    > /tmp/moonraker.conf.tmp && mv /tmp/moonraker.conf.tmp ${KLIPPER_CONFIG_HOME}/moonraker.conf
            restart_moonraker
        elif [ "${orig_section}" -ne 0 -a "${orig_origin2}" -ne 0 ]; then
            echo -e "${WARNING}Original [update_manager KlipperScreen] updated github origin to Happy Hare fork"
            cat ${KLIPPER_CONFIG_HOME}/moonraker.conf | sed -e "s%^${O2_GIT}%${HH_GIT}%" \
                    > /tmp/moonraker.conf.tmp && mv /tmp/moonraker.conf.tmp ${KLIPPER_CONFIG_HOME}/moonraker.conf
            restart_moonraker
        elif [ "${hh_section}" -ne 0 ]; then
            echo -e "${WARNING}Restoring [update_manager KlipperScreen] name for Happy Hare"
            cat ${KLIPPER_CONFIG_HOME}/moonraker.conf | sed -e " \
                s/^\[update_manager KlipperScreen-happy_hare\]/\[update_manager KlipperScreen\]/ \
                    " > /tmp/moonraker.conf.tmp && mv /tmp/moonraker.conf.tmp ${KLIPPER_CONFIG_HOME}/moonraker.conf
            restart_moonraker
	elif [ "${orig_section}" -eq 0 -a "${hh_section}" -eq 0 ]; then
            echo "" >> ${KLIPPER_CONFIG_HOME}/moonraker.conf
            while read -r line; do
                echo -e "${line}" >> ${KLIPPER_CONFIG_HOME}/moonraker.conf
            done < "${SRCDIR}/moonraker_update.txt"
            echo "" >> ${KLIPPER_CONFIG_HOME}/moonraker.conf
            restart_moonraker
        else
            echo -e "${WARNING}[update_manager KlipperScreen-happy_hare] already exist in moonraker.conf - skipping install"
        fi
# Not used anymore
#            echo -e "${WARNING}Original [update_manager KlipperScreen] commented out in moonraker.conf"
#            cat ${KLIPPER_CONFIG_HOME}/moonraker.conf | sed -e " \
#                /^\[update_manager KlipperScreen\]/,+7 s/^/#/; \
#                    " > /tmp/moonraker.conf.tmp && mv /tmp/moonraker.conf.tmp ${KLIPPER_CONFIG_HOME}/moonraker.conf
    else
        echo -e "${WARNING}Moonraker.conf not found!"
    fi
}


restart_klipperscreen() {
    echo -e "${INFO}Restarting KlipperScreen..."
    if [ "$OS_TYPE" = "$OS_FLYOS_FAST" ]; then
        sudo systemctl restart klipperscreen
    else
        sudo systemctl restart KlipperScreen
    fi
}


restart_moonraker() {
    echo -e "${INFO}Restarting Moonraker..."
    sudo systemctl restart moonraker
}


usage() {
    echo -e "${EMPHASIZE}"
    echo "Usage: $0 [-c <klipper_config_dir>] [-g <number_of_gates>] [-z]"
    echo
    echo "-z skip github check"
    echo
    exit 1
}


# Find SRCDIR from the pathname of this script
SRCDIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )"/ && pwd )"

while getopts "jc:g:z" arg; do
    case $arg in
        c) KLIPPER_CONFIG_HOME=${OPTARG};;
        g) num_gates=$OPTARG;;
	z) SKIP_UPDATE=1;;
	j) FORCE_JETBRAINS="--force";;
        *) usage;;
    esac
done

clear

if [ -z "$num_gates" ]; then
    num_gates=12
    echo
    echo -e "${WARNING}You didn't specify the number of gates with the -g <num_gates> argument so setting up for up to 12" >&2
    echo
fi

verify_not_root
[ -z "${SKIP_UPDATE}" ] && {
    self_update # Make sure the repo is up-to-date
}

install_jetbrains_fonts ${FORCE_JETBRAINS}

verify_home_dirs

install_klipper_screen

if [ "$OS_TYPE" = "$OS_FLYOS_FAST" ]; then
    echo -e "${WARNING}Skipping update manager install on ${OS_TYPE} system"
else
    install_update_manager
fi

echo -e "${EMPHASIZE}"
echo "Done.  Enjoy KlipperScreen Happy Hare Edition!"
echo -e "${INFO}"
echo '(\_/)'
echo '( *,*)'
echo '(")_(") Happy Hare Ready'
echo

