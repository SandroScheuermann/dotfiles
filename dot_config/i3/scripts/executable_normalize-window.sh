#!/bin/sh

# i3 keeps tiled containers normalized automatically; this also resets a
# floating container to a predictable size, matching the Hyprland shortcut.
i3-msg 'resize set 50 ppt 50 ppt' >/dev/null
