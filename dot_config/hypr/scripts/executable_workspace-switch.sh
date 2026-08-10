#!/bin/sh

config="$HOME/.config/hypr/workspace-domains.conf"
runtime_dir="${XDG_RUNTIME_DIR:-/tmp}"
state_file="$runtime_dir/hypr-workspace-domains.state"
lock_file="$runtime_dir/hypr-workspace-domains.lock"
theme_file="$HOME/.cache/hypr/domain-waybar.css"
fallback_wallpaper="$HOME/.config/hypr/wallpapers/wallpaper.jpg"

DEFAULT_WALLPAPER="$fallback_wallpaper"
DOMAIN_1_WALLPAPER="$fallback_wallpaper"
DOMAIN_2_WALLPAPER="$fallback_wallpaper"

if [ -r "$config" ]; then
  # shellcheck disable=SC1090
  . "$config"
fi

active_workspace_id() {
  hyprctl monitors -j | jq -r 'first(.[] | select(.focused == true) | .activeWorkspace.id)'
}

domain_for_workspace() {
  workspace_id="$1"

  if [ "$workspace_id" -ge 11 ] 2>/dev/null && [ "$workspace_id" -le 20 ]; then
    printf '%s\n' 2
  else
    printf '%s\n' 1
  fi
}

target_workspace() {
  domain="$1"
  slot="$2"
  printf '%s\n' "$(( (domain - 1) * 10 + slot ))"
}

hide_special_workspace() {
  special_name=$(hyprctl monitors -j | jq -r '.[] | select(.focused == true) | .specialWorkspace.name')

  case "$special_name" in
    special:*)
      special_name=${special_name#special:}
      hyprctl dispatch "hl.dsp.workspace.toggle_special(\"$special_name\")" >/dev/null
      ;;
  esac
}

notify_waybar() {
  pkill -x -RTMIN+8 waybar 2>/dev/null || true
}

sync_theme() {
  mkdir -p "$HOME/.cache/hypr"
  exec 9>"$lock_file"
  flock 9

  workspace_id=$(active_workspace_id)
  active_domain=$(domain_for_workspace "$workspace_id")
  workspaces=$(hyprctl workspaces -j)

  if printf '%s' "$workspaces" | jq -e 'any(.[]; .id >= 11 and .id <= 20 and .windows > 0)' >/dev/null; then
    domain_2_occupied=true
  else
    domain_2_occupied=false
  fi

  if [ "$active_domain" -eq 2 ]; then
    mode="domain-2"
    bar_bg="#101a2a"
    bar_border="#2b405e"
    tooltip_bg="#162238"
    hover="#21324d"
    workspace_active="#293f60"
    active="#9db9df"
    border_color="49698fff"
    if [ "$domain_2_occupied" = true ]; then
      wallpaper="$DOMAIN_2_WALLPAPER"
    else
      wallpaper="$DEFAULT_WALLPAPER"
    fi
  elif [ "$domain_2_occupied" = true ]; then
    mode="domain-1-dual"
    bar_bg="#211813"
    bar_border="#4b3529"
    tooltip_bg="#2a1e18"
    hover="#382820"
    workspace_active="#493329"
    active="#d2ad92"
    border_color="795640ff"
    wallpaper="$DOMAIN_1_WALLPAPER"
  else
    mode="domain-1-solo"
    bar_bg="#18191c"
    bar_border="#34363c"
    tooltip_bg="#222328"
    hover="#2d2f34"
    workspace_active="#3a3b40"
    active="#d4d4d6"
    border_color="ffffff28"
    wallpaper="$DEFAULT_WALLPAPER"
  fi

  if [ ! -f "$wallpaper" ]; then
    wallpaper="$fallback_wallpaper"
  fi

  previous_mode=""
  previous_wallpaper=""
  if [ -r "$state_file" ]; then
    IFS='|' read -r previous_mode previous_wallpaper < "$state_file"
  fi

  if [ "$mode" != "$previous_mode" ] || [ ! -f "$theme_file" ]; then
    temporary_theme="$theme_file.tmp.$$"
    {
      printf '@define-color domain_bg %s;\n' "$bar_bg"
      printf '@define-color domain_border %s;\n' "$bar_border"
      printf '@define-color tooltip_bg %s;\n' "$tooltip_bg"
      printf '@define-color hover %s;\n' "$hover"
      printf '@define-color workspace_active %s;\n' "$workspace_active"
      printf '@define-color workspace_hover %s;\n' "$hover"
      printf '@define-color active %s;\n' "$active"
    } > "$temporary_theme"
    mv "$temporary_theme" "$theme_file"

    hyprctl eval "hl.config({ general = { col = { active_border = \"rgba($border_color)\" } } })" >/dev/null
    pkill -x -USR2 waybar 2>/dev/null || true
  fi

  applied_wallpaper="$previous_wallpaper"
  if [ "$wallpaper" != "$previous_wallpaper" ]; then
    if hyprctl hyprpaper wallpaper ",$wallpaper,cover" >/dev/null 2>&1; then
      applied_wallpaper="$wallpaper"
    else
      applied_wallpaper=""
    fi
  fi

  printf '%s|%s\n' "$mode" "$applied_wallpaper" > "$state_file"
  notify_waybar
}

focus_slot() {
  slot="$1"
  workspace_id=$(active_workspace_id)
  domain=$(domain_for_workspace "$workspace_id")
  target=$(target_workspace "$domain" "$slot")

  hide_special_workspace
  hyprctl dispatch "hl.dsp.focus({ workspace = $target })" >/dev/null
  sync_theme
}

move_to_slot() {
  slot="$1"
  workspace_id=$(active_workspace_id)
  domain=$(domain_for_workspace "$workspace_id")
  target=$(target_workspace "$domain" "$slot")

  hyprctl dispatch "hl.dsp.window.move({ workspace = $target })" >/dev/null
  sync_theme
}

switch_domain() {
  domain="$1"
  target=$(target_workspace "$domain" 1)

  hide_special_workspace
  hyprctl dispatch "hl.dsp.focus({ workspace = $target })" >/dev/null
  sync_theme
}

cycle_slot() {
  direction="$1"
  workspace_id=$(active_workspace_id)
  domain=$(domain_for_workspace "$workspace_id")
  slot=$(( workspace_id - (domain - 1) * 10 ))
  slot=$(( (slot - 1 + direction + 10) % 10 + 1 ))
  focus_slot "$slot"
}

print_status() {
  slot="$1"
  workspace_id=$(active_workspace_id)
  domain=$(domain_for_workspace "$workspace_id")
  target=$(target_workspace "$domain" "$slot")
  workspaces=$(hyprctl workspaces -j)

  if [ "$workspace_id" -eq "$target" ]; then
    class="active"
    printf '{"text":"%s","class":"%s","tooltip":"Workspace %s"}\n' "$slot" "$class" "$slot"
  elif ! printf '%s' "$workspaces" | jq -e --argjson target "$target" 'any(.[]; .id == $target and .windows > 0)' >/dev/null; then
    printf '{"text":"","class":"hidden","tooltip":false}\n'
  else
    class="occupied"
    printf '{"text":"%s","class":"%s","tooltip":"Workspace %s"}\n' "$slot" "$class" "$slot"
  fi
}

action="${1:-}"
value="${2:-}"

case "$action" in
  focus)
    [ "$value" -ge 1 ] 2>/dev/null && [ "$value" -le 10 ] || exit 1
    focus_slot "$value"
    ;;
  move)
    [ "$value" -ge 1 ] 2>/dev/null && [ "$value" -le 10 ] || exit 1
    move_to_slot "$value"
    ;;
  domain)
    [ "$value" -eq 1 ] 2>/dev/null || [ "$value" -eq 2 ] 2>/dev/null || exit 1
    switch_domain "$value"
    ;;
  next)
    cycle_slot 1
    ;;
  previous)
    cycle_slot -1
    ;;
  status)
    [ "$value" -ge 1 ] 2>/dev/null && [ "$value" -le 10 ] || exit 1
    print_status "$value" 2>/dev/null
    ;;
  sync)
    sync_theme
    ;;
  *)
    exit 1
    ;;
esac
