# Dotfiles

Personal dotfiles managed with [chezmoi](https://www.chezmoi.io/).

This repository is a chezmoi source tree. It stores files using chezmoi's naming conventions, for example:

- `dot_config/hypr` becomes `~/.config/hypr`
- `dot_config/i3` becomes `~/.config/i3` when the `i3` session is selected
- `repos/waybarcfgs/minimal-waybar` becomes `~/repos/waybarcfgs/minimal-waybar`
- `executable_script.sh` becomes an executable `script.sh`
- `*.tmpl` files are rendered as templates before being written

## What's Included

- Hyprland configuration and scripts
- i3/X11 configuration and scripts as an alternative session
- Hyprlauncher / Hyprtoolkit theme
- Waybar configuration
- Polybar, Rofi, and Dunst configuration for i3
- Minimal Waybar setup under `~/repos/waybarcfgs/minimal-waybar`
- SwayNC styling/configuration
- Wofi fallback styling/configuration
- Fish shell configuration
- Kitty configuration
- Btop theme/configuration
- Fastfetch configuration
- GTK settings
- Wlogout configuration
- Starship prompt configuration
- XDG user directory settings
- Curated Hyprpaper wallpaper

## What's Intentionally Not Included

- Browser profiles: Brave, Chromium, Firefox
- Cache directories
- Session/runtime state
- SSH keys
- Passwords, API keys, tokens, and private secrets
- Remmina/Freerdp connection profiles
- PulseAudio/PipeWire runtime state
- Large screenshots or generated files (except the curated wallpaper)

## Install chezmoi

On Arch/CachyOS:

```sh
sudo pacman -S chezmoi
```

Check the installation:

```sh
chezmoi --version
```

## One-command Setup

On a fresh CachyOS installation, initialize and apply the repo:

```sh
chezmoi init --apply https://github.com/SandroScheuermann/dotfiles.git
```

The bootstrap script asks for sudo access on first setup and when the rendered
desktop session changes, then:

- installs all core packages;
- installs optional packages except `steam` and `fprintd`;
- disables greetd and removes Noctalia packages when present;
- enables NetworkManager, power-profiles-daemon, and SDDM;
- installs the selected desktop session through the rendered package manifest;
- removes stale session configuration through `.chezmoiremove`.

The AUR manifest is intentionally not installed automatically. Review it and
install its packages separately with `paru`.

## Install Packages On CachyOS

The package manifests intentionally do not include kernels, GPU drivers, or
hardware-specific firmware. Install those for the new machine after checking
its hardware.

From the source directory:

```sh
grep -Ev '^[[:space:]]*(#|$)' packages/cachyos-core.txt | sudo pacman -S --needed -
grep -Ev '^[[:space:]]*(#|$)' packages/cachyos-optional.txt | sudo pacman -S --needed -
grep -Ev '^[[:space:]]*(#|$)' packages/cachyos-aur.txt | paru -S --needed -
```

Remove optional lines before installing anything you do not want. The AUR
manifest is separate because `pacman` cannot install AUR packages.

Enable the core desktop services after installation:

```sh
sudo systemctl enable --now NetworkManager
sudo systemctl enable sddm
sudo systemctl enable --now power-profiles-daemon
```

Enable these only when their packages are installed and needed:

```sh
sudo systemctl enable --now docker
sudo systemctl enable --now bluetooth
```

## Use This Local Source Folder

From this machine, initialize chezmoi with this folder as the source:

```sh
chezmoi init --source ~/dotfiles-chezmoi
```

During initialization, choose the machine profile:

- `desktop`: forces the performance power profile and hides notebook-only status modules.
- `notebook`: enables battery, brightness, and selectable power profiles when supported by the hardware.

The same initialization also asks for the desktop session:

- `hyprland`: the current Wayland profile with Hyprland, Waybar, SwayNC, and Hypr utilities.
- `i3`: an X11 profile with i3, Polybar, Rofi, Dunst, and X11 replacements for the Hyprland utilities.

The X11 profile keeps the same Super-key shortcuts and workspace domains. Each monitor
has independent D1/D2 domains with slots 1-10, and the focused monitor receives keyboard
workspace shortcuts. Polybar controls act on the monitor that owns the bar.

The choice is stored only on the local machine in `~/.config/chezmoi/chezmoi.toml`:

```toml
[data]
machineType = "desktop"
desktopSession = "hyprland"
```

To change a profile later, edit `machineType` or `desktopSession`, then run `chezmoi apply`.
Switching `desktopSession` changes the rendered package manifest and session files; it
does not automatically uninstall packages belonging to the other session.

Preview what would change:

```sh
chezmoi diff
```

Apply the dotfiles:

```sh
chezmoi apply
```

Edit a managed file through chezmoi:

```sh
chezmoi edit ~/.config/hypr/hyprland.lua
chezmoi apply
```

Add or update a file from your home directory into the source tree:

```sh
chezmoi add ~/.config/hypr/hyprland.lua
chezmoi add ~/.config/i3/config
```

See managed files:

```sh
chezmoi managed
```

## Push To Your Git Remote

Initialize Git if needed:

```sh
cd ~/dotfiles-chezmoi
git init
git add .
git status
git commit -m "Add initial dotfiles"
```

Create an empty repository on GitHub/GitLab, then add it as a remote:

```sh
git remote add origin git@github.com:YOUR_USER/YOUR_REPO.git
git branch -M main
git push -u origin main
```

## Restore On A New Machine

Install chezmoi first, then initialize from your Git repository:

```sh
chezmoi init git@github.com:YOUR_USER/YOUR_REPO.git
chezmoi diff
chezmoi apply
```

If you prefer cloning manually:

```sh
git clone git@github.com:YOUR_USER/YOUR_REPO.git ~/dotfiles-chezmoi
chezmoi init --source ~/dotfiles-chezmoi
chezmoi diff
chezmoi apply
```

## Notes

Some files use chezmoi templates to avoid hardcoding this machine's home path. For example, `{{ .chezmoi.homeDir }}` is rendered as the current user's home directory when applying.

Before making the repository public, review everything with:

```sh
grep -RniE 'token|secret|password|api[_-]?key|private|bearer' .
git status
```
