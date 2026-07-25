#!/bin/sh

if ! command -v hyprsunset >/dev/null 2>&1; then
  notify-send "Night light" "Install hyprsunset to enable night light." 2>/dev/null
  exit 0
fi

if pgrep -x hyprsunset >/dev/null 2>&1; then
  pkill -x hyprsunset
  notify-send "Night light" "Off" 2>/dev/null
else
  hyprsunset -t 4500 >/dev/null 2>&1 &
  notify-send "Night light" "On: 4500K" 2>/dev/null
fi
