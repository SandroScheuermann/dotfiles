if test -f /usr/share/cachyos-fish-config/cachyos-config.fish
    source /usr/share/cachyos-fish-config/cachyos-config.fish
end

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
