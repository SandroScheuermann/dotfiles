#!/bin/sh

"$HOME/.config/hypr/scripts/workspace-switch.sh" sync

exec waybar \
  -c "$HOME/repos/waybarcfgs/minimal-waybar/waybar/config-simple" \
  -s "$HOME/repos/waybarcfgs/minimal-waybar/waybar/style-simple.css"
