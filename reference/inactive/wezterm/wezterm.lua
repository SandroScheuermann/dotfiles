local wezterm = require("wezterm")

local config = wezterm.config_builder()

config.font = wezterm.font("JetBrainsMono Nerd Font")
config.font_size = 20.0

config.window_background_opacity = 0.78
config.window_decorations = "RESIZE"
config.window_padding = {
  left = 8,
  right = 8,
  top = 8,
  bottom = 8,
}

config.colors = {
  foreground = "#f7faff",
  background = "#00081c",
  cursor_bg = "#589df6",
  cursor_fg = "#00081c",
  cursor_border = "#589df6",
  selection_fg = "#f7faff",
  selection_bg = "#1f4f8f",
  ansi = {
    "#061027",
    "#ff6b7a",
    "#40efa9",
    "#f4c56a",
    "#589df6",
    "#b98cff",
    "#6ee7ff",
    "#dce7ff",
  },
  brights = {
    "#51607a",
    "#ff8f9a",
    "#73ffc4",
    "#ffd98a",
    "#82b8ff",
    "#d2b2ff",
    "#9af0ff",
    "#ffffff",
  },
}

config.hide_tab_bar_if_only_one_tab = true
config.use_fancy_tab_bar = false

wezterm.on("format-window-title", function(tab, pane)
  local cwd = pane.current_working_dir

  if cwd then
    return cwd.file_path
  end

  return tab.active_pane.title
end)

return config
