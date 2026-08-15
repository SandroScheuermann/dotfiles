#!/bin/sh

kind=${1:-}

case "$kind" in
    output)
        list_type=sinks
        prompt="Audio output"
        ;;
    input)
        list_type=sources
        prompt="Audio input"
        ;;
    *)
        exit 2
        ;;
esac

for command in pactl jq rofi; do
    if ! command -v "$command" >/dev/null 2>&1; then
        notify-send "Audio devices" "Install $command to use the device selector." 2>/dev/null
        exit 1
    fi
done

if [ "$kind" = output ]; then
    default_device=$(pactl get-default-sink 2>/dev/null)
else
    default_device=$(pactl get-default-source 2>/dev/null)
fi

devices=$(pactl --format=json list "$list_type") || exit 1

if [ "$kind" = input ]; then
    devices=$(printf '%s' "$devices" | jq '[.[] | select(.monitor_source == "")]') || exit 1
fi

entries=$(printf '%s' "$devices" | jq -r --arg current "$default_device" '
    to_entries[] |
    "\(.key + 1)  \(if .value.name == $current then "*" else " " end) \(.value.description)"
') || exit 1

[ -n "$entries" ] || {
    notify-send "Audio devices" "No $kind devices are available." 2>/dev/null
    exit 0
}

selected=$(printf '%s\n' "$entries" | rofi \
    -dmenu \
    -i \
    -no-custom \
    -p "$prompt" \
    -theme "$HOME/.config/rofi/theme.rasi") || exit 0

number=${selected%% *}
case "$number" in
    ''|*[!0-9]*) exit 1 ;;
esac

device=$(printf '%s' "$devices" | jq -r --argjson index "$((number - 1))" '.[$index].name // empty')
[ -n "$device" ] || exit 1

if [ "$kind" = output ]; then
    pactl set-default-sink "$device" || exit 1
    pactl list short sink-inputs | while IFS="$(printf '\t')" read -r stream _; do
        [ -n "$stream" ] && pactl move-sink-input "$stream" "$device"
    done
else
    pactl set-default-source "$device" || exit 1
    pactl list short source-outputs | while IFS="$(printf '\t')" read -r stream _; do
        [ -n "$stream" ] && pactl move-source-output "$stream" "$device"
    done
fi
