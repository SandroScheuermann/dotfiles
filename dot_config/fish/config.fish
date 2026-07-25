source /usr/share/cachyos-fish-config/cachyos-config.fish

# Disable the CachyOS fastfetch greeting on new terminals.
function fish_greeting
end

function fish_title
    pwd
end

# bun
set --export BUN_INSTALL "$HOME/.bun"
set --export PATH $BUN_INSTALL/bin $PATH

set --export COLORTERM truecolor

if command -q starship
    starship init fish | source
end

if command -q zoxide
    zoxide init fish | source
end

function sopencode
    sudo env \
        HOME="$HOME" \
        XDG_CONFIG_HOME="$HOME/.config" \
        XDG_DATA_HOME="$HOME/.local/share" \
        XDG_STATE_HOME="$HOME/.local/state" \
        XDG_CACHE_HOME="$HOME/.cache" \
        opencode $argv
end
