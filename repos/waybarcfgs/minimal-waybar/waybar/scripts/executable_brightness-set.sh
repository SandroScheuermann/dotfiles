#!/bin/sh

min=5
step=1
current=$(brightnessctl -m | cut -d, -f4 | tr -d '%')

case "$1" in
  up)
    next=$((current + step))
    ;;
  down)
    next=$((current - step))
    ;;
  *)
    exit 1
    ;;
esac

if [ "$next" -lt "$min" ]; then
  next=$min
fi

if [ "$next" -gt 100 ]; then
  next=100
fi

brightnessctl set "${next}%"
pkill -RTMIN+9 waybar
