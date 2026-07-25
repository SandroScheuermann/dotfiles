#!/bin/sh

if command -v hyprlauncher >/dev/null 2>&1; then
  if pgrep -x hyprlauncher >/dev/null 2>&1; then
    exec hyprlauncher --toggle --quiet
  fi

  exec hyprlauncher --quiet
fi

exec wofi --show drun
