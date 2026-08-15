#!/usr/bin/env bash

set -u

focused_output() {
    i3-msg -t get_workspaces | jq -r 'first(.[] | select(.focused == true) | .output) // empty'
}

target_output() {
    if [[ -n "${MONITOR:-}" ]]; then
        printf '%s\n' "$MONITOR"
    else
        focused_output
    fi
}

visible_workspace_name() {
    local output=$1

    i3-msg -t get_workspaces | jq -r --arg output "$output" 'first(.[] | select(.output == $output and .visible == true) | .name) // empty'
}

workspace_name() {
    local domain=$1
    local output=$2
    local slot=$3

    printf 'd%s:%s:%s\n' "$domain" "$output" "$slot"
}

domain_for_workspace_name() {
    local name=$1

    if [[ "$name" =~ ^d([12]): ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
    elif [[ "$name" =~ ^([0-9]+)$ ]] && ((BASH_REMATCH[1] >= 11 && BASH_REMATCH[1] <= 20)); then
        printf '2\n'
    else
        printf '1\n'
    fi
}

slot_for_workspace_name() {
    local name=$1
    local number

    if [[ "$name" =~ ^d[12]:[^:]+:([1-9]|10)$ ]]; then
        printf '%s\n' "${BASH_REMATCH[1]}"
    elif [[ "$name" =~ ^([0-9]+)$ ]]; then
        number=${BASH_REMATCH[1]}
        if ((number >= 11 && number <= 20)); then
            printf '%s\n' "$((number - 10))"
        elif ((number >= 1 && number <= 10)); then
            printf '%s\n' "$number"
        else
            printf '1\n'
        fi
    else
        printf '1\n'
    fi
}

workspace_has_window() {
    local target=$1

    i3-msg -t get_tree | jq -e --arg target "$target" '
        [
            .. | objects
            | select(.type == "workspace" and .name == $target)
            | .. | objects
            | select((.type == "con" or .type == "floating_con") and .window != null)
        ] | length > 0
    ' >/dev/null
}

focused_class() {
    i3-msg -t get_tree | jq -r 'first(.. | objects | select(.focused == true and .window_properties != null) | .window_properties.class) // empty'
}

hide_special_workspace() {
    case "$(focused_class)" in
        md.Obsidian|obsidian|winboat|winboat-*)
            i3-msg move scratchpad >/dev/null
            ;;
    esac
}

focus_slot() {
    local slot=$1
    local output current domain target

    output=$(target_output)
    [[ -n "$output" ]] || exit 1
    current=$(visible_workspace_name "$output")
    domain=$(domain_for_workspace_name "$current")
    target=$(workspace_name "$domain" "$output" "$slot")

    hide_special_workspace
    # i3 creates a new workspace on the focused output. Focus the requested
    # output first so a click on another bar never displaces this monitor.
    i3-msg "focus output \"$output\"" >/dev/null
    i3-msg "workspace \"$target\"" >/dev/null
    i3-msg "move workspace to output \"$output\"" >/dev/null
}

move_to_slot() {
    local slot=$1
    local output current domain target

    output=$(target_output)
    [[ -n "$output" ]] || exit 1
    current=$(visible_workspace_name "$output")
    domain=$(domain_for_workspace_name "$current")
    target=$(workspace_name "$domain" "$output" "$slot")

    i3-msg "move container to workspace \"$target\"" >/dev/null
}

switch_domain() {
    local domain=$1
    local output target

    output=$(target_output)
    [[ -n "$output" ]] || exit 1
    target=$(workspace_name "$domain" "$output" 1)

    hide_special_workspace
    i3-msg "focus output \"$output\"" >/dev/null
    i3-msg "workspace \"$target\"" >/dev/null
    i3-msg "move workspace to output \"$output\"" >/dev/null
}

cycle_slot() {
    local direction=$1
    local output current domain slot

    output=$(target_output)
    [[ -n "$output" ]] || exit 1
    current=$(visible_workspace_name "$output")
    domain=$(domain_for_workspace_name "$current")
    slot=$(slot_for_workspace_name "$current")
    slot=$(( (slot - 1 + direction + 10) % 10 + 1 ))

    MONITOR="$output" focus_slot "$slot"
}

print_status() {
    local slot=$1
    local output current domain target

    output=$(target_output)
    [[ -n "$output" ]] || exit 1
    current=$(visible_workspace_name "$output")
    domain=$(domain_for_workspace_name "$current")
    target=$(workspace_name "$domain" "$output" "$slot")

    if [[ "$current" == "$target" ]]; then
        printf '%%{B#3a3b40}%%{F#d4d4d6} %s %%{F-}%%{B-}\n' "$slot"
    elif workspace_has_window "$target"; then
        printf '%%{F#d4d4d6} %s %%{F-}\n' "$slot"
    else
        printf '\n'
    fi
}

migrate_visible_workspaces() {
    local output name number domain slot target

    while IFS=$'\t' read -r output name number; do
        [[ "$name" =~ ^[0-9]+$ ]] || continue

        if ((number >= 1 && number <= 10)); then
            domain=1
            slot=$number
        elif ((number >= 11 && number <= 20)); then
            domain=2
            slot=$((number - 10))
        else
            continue
        fi

        target=$(workspace_name "$domain" "$output" "$slot")
        i3-msg "rename workspace \"$name\" to \"$target\"" >/dev/null
    done < <(i3-msg -t get_workspaces | jq -r '.[] | select(.visible == true) | [.output, .name, .num] | @tsv')
}

action=${1:-}
value=${2:-}

case "$action" in
    focus)
        [[ "$value" =~ ^([1-9]|10)$ ]] || exit 1
        focus_slot "$value"
        ;;
    move)
        [[ "$value" =~ ^([1-9]|10)$ ]] || exit 1
        move_to_slot "$value"
        ;;
    domain)
        [[ "$value" == 1 || "$value" == 2 ]] || exit 1
        switch_domain "$value"
        ;;
    next)
        cycle_slot 1
        ;;
    previous)
        cycle_slot -1
        ;;
    status)
        [[ "$value" =~ ^([1-9]|10)$ ]] || exit 1
        print_status "$value"
        ;;
    domain-status)
        output=$(target_output)
        [[ -n "$output" ]] || exit 1
        printf 'D%s\n' "$(domain_for_workspace_name "$(visible_workspace_name "$output")")"
        ;;
    migrate)
        migrate_visible_workspaces
        ;;
    *)
        exit 1
        ;;
esac
