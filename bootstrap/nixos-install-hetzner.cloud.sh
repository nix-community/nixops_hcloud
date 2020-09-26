#! /usr/bin/env bash
# Based on https://gist.github.com/nh2/c02612e05d1a0f5dc9fd50dda04b3e48

# Script to install NixOS from the Hetzner Cloud NixOS bootable ISO image.
# Wipes the disk!
# Tested with Hetzner's `NixOS 20.03 (amd64/minimal)` ISO image.
#
# Run like:
#
#     curl https://raw.githubusercontent.com/RoGryza/nixops_hetznercloud/master/bootstrap/nixos-install-hetzner-cloud.sh | sudo bash
#
# To run it from the Hetzner Cloud web terminal without typing it down,
# use `xdotoool` (you have e.g. 3 seconds to focus the window):
#
#     sleep 3 && xdotool type --delay 50 'curl ...'
#
# (If you use a non-US keyboard, run `setxkbmap us` before `xdotool`. You can reset your keyboard
# map afterwards.)

set -e

mkfs.ext4 /dev/sda1

mount /dev/sda1 /mnt

nixos-generate-config --root /mnt
REPO="https://raw.githubusercontent.com/RoGryza/nixops_hetznercloud/master/"
curl "$REPO/bootstrap/configuration.nix" > /mnt/etc/nixos/configuration.nix
curl "$REPO/bootstrap/fetchHetznerKeys.nix" > /mnt/etc/nixos/fetchHetznerKeys.nix

nixos-install --no-root-passwd

reboot
