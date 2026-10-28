#!/usr/bin/env python3
"""One-time allowlisted capture into THIS project; never run by bootstrap.

No credentials, environment values, personal projects, application profiles,
Git history, or arbitrary ~/.config traversal. Text is checked BEFORE writing.
"""
import json
import os
import re
import subprocess
from pathlib import Path
from safety import check_text

ROOT = Path(__file__).resolve().parents[1]
HOME = Path.home()
SOURCE = ROOT / "chezmoi"
EXCLUDED = {"chromium", "firefox", "spotify-launcher", "steam"}
GROUPS = {
    "core": "base git chezmoi openssh rsync sudo less man-db man-pages ripgrep wget unzip neovim yazi",
    "shell": "kitty fish zsh cachyos-fish-config cachyos-zsh-config starship zoxide bash-completion btop fastfetch duf glances micro nano nano-syntax-highlighting vim",
    "desktop": "hyprland hypridle hyprlock hyprpaper hyprlauncher hyprshot hyprsunset waybar swaync wofi wlogout cliphist wl-clipboard uwsm xorg-xwayland xdg-desktop-portal-hyprland xdg-user-dirs polkit-kde-agent pipewire-alsa pipewire-pulse wireplumber pavucontrol playerctl brightnessctl power-profiles-daemon qt6ct nwg-look ttf-jetbrains-mono-nerd noto-fonts noto-fonts-emoji papirus-icon-theme",
    "apps": "brave-bin dolphin obsidian vlc vlc-plugins-all ffmpegthumbnailer",
    "work": "slack-desktop-wayland teams-for-linux tailscale twingate",
    "remote": "remmina freerdp meld networkmanager-openvpn xl2tpd",
    "dev": "base-devel cmake docker docker-compose lazydocker nodejs python python-defusedxml python-packaging rustup jdk21-openjdk jre-openjdk github-cli opencode",
    "android": "android-studio",
    "network": "networkmanager bluez bluez-utils bluez-obex bluez-hid2hci bluez-libs wpa_supplicant iwd netctl bind inetutils ethtool nss-mdns modemmanager ufw ufw-extras dnsmasq nfs-utils",
    "visuals": "awesome-terminal-fonts cantarell-fonts noto-fonts-cjk ttf-bitstream-vera ttf-dejavu ttf-liberation ttf-meslo-nerd ttf-opensans woff2-font-awesome",
    "cpu-intel": "intel-ucode intel-lpmd",
    "gpu-intel": "intel-media-driver vulkan-intel lib32-vulkan-intel vpl-gpu-rt",
    "graphics": "mesa-utils lib32-mesa opencl-mesa lib32-opencl-mesa",
    "boot": "linux-cachyos linux-cachyos-headers linux-cachyos-lts linux-cachyos-lts-headers limine limine-mkinitcpio-hook limine-snapper-sync mkinitcpio plymouth cachyos-plymouth-bootanimation cachyos-plymouth-theme cachyos-hooks cachyos-snapper-support chwd os-prober efibootmgr efitools",
    "storage": "btrfs-assistant btrfs-progs cryptsetup device-mapper dmraid dosfstools e2fsprogs exfatprogs f2fs-tools fsarchiver hdparm jfsutils lvm2 mdadm mtools nilfs-utils sg3_utils smartmontools snapper xfsprogs",
}


def write(relative, data):
    path = ROOT / relative
    if isinstance(data, str):
        check_text(data, str(relative))
        data = data.encode()
    if path.exists():
        if path.is_file() and not path.is_symlink() and path.read_bytes() == data:
            return
        raise RuntimeError(f"Capture não sobrescreve arquivos diferentes: {relative}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)


def json_write(relative, data):
    write(relative, json.dumps(data, ensure_ascii=False, indent=2) + "\n")


def decode_fish_value(value):
    if value == r"\x1d": return []
    pattern = r"\\(x[0-9a-fA-F]{2}|u[0-9a-fA-F]{4}|U[0-9a-fA-F]{8}|[\\abefnrtv])"
    simple = {"\\": "\\", "a": "\a", "b": "\b", "e": "\x1b", "f": "\f", "n": "\n", "r": "\r", "t": "\t", "v": "\v"}
    result = []
    for item in value.split(r"\x1e"):
        if re.search(r"\\", re.sub(pattern, "", item)):
            raise ValueError("Escape Fish inesperado; nenhum valor será exportado")
        result.append(re.sub(pattern, lambda match: simple[match[1]] if match[1] in simple else chr(int(match[1][1:], 16)), item))
    return result


def capture_prompt_settings():
    """Extract ONLY typed Pure appearance settings, never raw universal state."""
    path = HOME / ".config/fish/fish_variables"
    if not path.is_file(): return
    lines = ["# Selected Pure appearance settings; global/session only, not raw universal state."]
    count = 0
    for line in path.read_text().splitlines():
        match = re.fullmatch(r"SETUVAR(?: --export)? (pure_[A-Za-z0-9_]+):(.*)", line)
        if not match: continue
        name, encoded = match.groups()
        if not re.search(r"(?:color|symbol|enable|show|threshold|begin_prompt|separate_prompt|only|reverse|truncate)", name): continue
        if re.search(r"token|secret|password|credential|auth|key", name, re.I): continue
        values = decode_fish_value(encoded)
        if any(len(value) > 256 or any(ord(c) < 32 or ord(c) == 127 for c in value) for value in values):
            raise ValueError("Valor de aparência não suportado; nenhum valor será exportado")
        check_text("\n".join(values), "Preferências Pure selecionadas")
        # All values are inert single-quoted literals, never evaluated as code.
        quoted = ["'" + value.replace("\\", "\\\\").replace("'", "\\'") + "'" for value in values]
        lines.append("set --global " + name + (" " + " ".join(quoted) if quoted else ""))
        count += 1
    if count:
        write("chezmoi/dot_config/fish/conf.d/portable-prompt.fish", "\n".join(lines) + "\n")
    print(f"Preferências visuais Pure: {count}; nenhum estado universal bruto ou valor exibido.")


def query(*args):
    return subprocess.run(args, capture_output=True, text=True, check=False).stdout


def fields(text):
    result = []
    current = {}
    last = None
    for line in text.splitlines() + [""]:
        if not line.strip():
            if current:
                result.append(current)
            current, last = {}, None
        elif line[:1].isspace() and last:
            current[last] += " " + line.strip()
        elif ":" in line:
            key, value = line.split(":", 1)
            last = key.strip()
            current[last] = value.strip()
    return result


def capture_packages():
    os.environ["LC_ALL"] = "C"
    explicit = set(query("pacman", "-Qqe").split())
    foreign = set(query("pacman", "-Qqm").split())
    orphans = set(query("pacman", "-Qdtq").split())
    groups = {n: group for group, names in GROUPS.items() for n in names.split()}
    sync = {p["Name"]: p["Repository"] for p in fields(query("pacman", "-Si")) if "Name" in p}
    snapshot, selected = [], []
    for p in fields(query("pacman", "-Qi")):
        name = p["Name"]
        entry = {"name": name, "version": p["Version"], "purpose": p["Description"], "reason": "explicit" if name in explicit else "dependency", "required_by": [] if p.get("Required By") == "None" else p.get("Required By", "").split(), "foreign": name in foreign, "orphan": name in orphans, "repository": sync.get(name), "decision": "exclude" if name in EXCLUDED else "keep"}
        snapshot.append(entry)
        if name in EXCLUDED or (name not in explicit and name not in {"fish", "zsh"} and name not in orphans):
            continue
        component = groups.get(name, "compatibility" if name in orphans else "extras")
        condition = "always"
        if name.startswith("cachyos-") or name in {"chwd", "linux-cachyos", "linux-cachyos-headers", "linux-cachyos-lts", "linux-cachyos-lts-headers"}:
            condition = "cachyos"
        if component == "cpu-intel": condition = "intel_cpu"
        if component == "gpu-intel": condition = "intel_gpu"
        selected.append({"name": name, "component": component, "condition": condition, "source": "aur" if name in {"android-studio", "debtap", "twingate", "python-ewmh"} else "unresolved" if name in foreign else "repository"})
    # Essential runtime dependencies that package-reason-only exports miss.
    runtime = {"jq": "desktop", "grim": "desktop", "slurp": "desktop", "libnotify": "desktop", "qt6-wayland": "desktop", "pipewire": "desktop", "xdg-desktop-portal-gtk": "desktop", "curl": "core", "networkmanager": "desktop", "bluetooth": "desktop", "sddm": "desktop", "satty": "desktop", "swappy": "desktop", "bun": "dev", "uv": "dev"}
    runtime.pop("bluetooth")  # service name, not a package
    for name, component in runtime.items():
        existing = next((p for p in selected if p["name"] == name), None)
        if existing:
            existing["component"] = component
        else:
            selected.append({"name": name, "component": component, "condition": "always", "source": "repository"})
    json_write("inventory/installed.json", snapshot)
    json_write("inventory/packages.yml", {"format": "JSON-compatible YAML", "packages": sorted(selected, key=lambda p: p["name"]), "excluded": sorted(EXCLUDED), "excluded_manual": ["spotify_player"]})
    print(f"Pacotes: {len(snapshot)} inventariados; {len(selected)} entradas modulares; sem valores privados.")


def import_text(source, destination, transform=None):
    path = HOME / source
    if not path.is_file() or path.is_symlink():
        return
    text = path.read_text()
    check_text(text, source)
    # Never turn unreviewed pre-existing template code into executable templates.
    if "{{" in text or "}}" in text:
        raise ValueError(f"Template preexistente exige revisão: {source}")
    if transform:
        text = transform(text)
    text = text.replace(str(HOME), "{{ .portable.home }}")
    if "{{" in text and not destination.endswith(".tmpl"):
        destination += ".tmpl"
    write("chezmoi/" + destination, text)


def strip_jpeg_metadata(data):
    if not data.startswith(b"\xff\xd8"):
        raise ValueError("Wallpaper não é JPEG")
    out, i = bytearray(data[:2]), 2
    while i < len(data):
        start = i
        if data[i] != 255: raise ValueError("JPEG inválido")
        while data[i] == 255: i += 1
        marker = data[i]; i += 1
        if marker == 0xDA:
            out.extend(data[start:]); return bytes(out)
        if marker in {0xD9, 0x01} or 0xD0 <= marker <= 0xD7:
            out.extend(data[start:i]); continue
        size = int.from_bytes(data[i:i+2], "big")
        if size < 2 or i + size > len(data): raise ValueError("JPEG truncado")
        # Drop EXIF/XMP/IPTC/comments, retain image/ICC/JFIF information.
        if marker not in {0xE1, 0xED, 0xFE}:
            out.extend(data[start:i+size])
        i += size
    raise ValueError("JPEG sem dados de imagem")


def jsonc(text):
    # Strip comments outside JSON strings, then trailing commas outside strings.
    out, i, string = [], 0, False
    while i < len(text):
        c = text[i]
        if string:
            out.append(c)
            if c == "\\" and i + 1 < len(text):
                i += 1; out.append(text[i])
            elif c == '"': string = False
        elif c == '"': string = True; out.append(c)
        elif text[i:i+2] == "//":
            i = text.find("\n", i)
            if i == -1: break
            out.append("\n")
        elif text[i:i+2] == "/*":
            end = text.find("*/", i+2)
            if end == -1: raise ValueError("Comentário JSONC sem fechamento")
            i = end + 1
        elif c == "," and re.match(r"\s*[}\]]", text[i+1:]): pass
        else: out.append(c)
        i += 1
    return json.loads("".join(out))


def capture_configs():
    def hyprland(text):
        text = re.sub(r"plugin:hyprglass \{.*?\n\}", "# Plugin hyprglass inativo omitido; nenhum plugin é instalado automaticamente.", text, flags=re.S)
        text = text.replace(str(HOME) + "/repos/waybarcfgs/minimal-waybar/waybar/", str(HOME) + "/.config/waybar/")
        text = text.replace("config-simple", "config.jsonc").replace("style-simple.css", "style.css")
        text = text.replace("env WAYLAND_DISPLAY=wayland-1 ", "")
        text = text.replace("kb_layout = us", "kb_layout = {{ .portable.keyboard_layout }}").replace("kb_variant = intl", "kb_variant = {{ .portable.keyboard_variant }}")
        text = text.replace("bind = $mainMod, O, exec,", "{{ if .portable.obsidian }}\nbind = $mainMod, O, exec,")
        text = text.replace("scripts/obsidian-special.sh\n", "scripts/obsidian-special.sh\n{{ end }}\n")
        text = text.replace("windowrule = match:class ^(obsidian)$, workspace special:obsidian", "{{ if .portable.obsidian }}\nwindowrule = match:class ^(obsidian)$, workspace special:obsidian\n{{ end }}")
        return text + '\n# Perfis portáveis e ajustes manuais locais\nsource = {{ .portable.home }}/.config/hypr/portable.conf\nsource = {{ .portable.home }}/.config/hypr/local.conf\n'
    import_text(".config/hypr/hyprland.conf", "dot_config/hypr/hyprland.conf.tmpl", hyprland)
    # hypridle has an explicitly authored portable template, not copied policy.
    for name in ["hyprlock", "hyprpaper", "hyprlauncher", "hyprtoolkit"]:
        transform = (lambda t: t.replace('enabled = true\n        ready_message', 'enabled = {{ .portable.fingerprint }}\n        ready_message')) if name == "hyprlock" else None
        import_text(f".config/hypr/{name}.conf", f"dot_config/hypr/{name}.conf.tmpl", transform)
    for name in ["clipboard-menu", "launcher", "night-toggle", "obsidian-special", "workspace-switch", "screenshot-edit"]:
        import_text(f".config/hypr/scripts/{name}.sh", f"dot_config/hypr/scripts/executable_{name}.sh")
    for name in ["config.fish", "conf.d/fish_frozen_theme.fish", "functions/fish_prompt.fish", "functions/jiggler.fish"]:
        import_text(".config/fish/" + name, "dot_config/fish/" + name, (lambda t: t.replace('source /usr/share/cachyos-fish-config/cachyos-config.fish', 'if test -f /usr/share/cachyos-fish-config/cachyos-config.fish\n    source /usr/share/cachyos-fish-config/cachyos-config.fish\nend')) if name == "config.fish" else None)
    for rel in ["kitty/kitty.conf", "nvim/init.lua", "yazi/yazi.toml", "micro/settings.json", "btop/btop.conf", "btop/themes/minimal-dark-glass.theme", "fastfetch/config.jsonc", "gtk-3.0/settings.ini", "gtk-4.0/settings.ini", "qt6ct/qt6ct.conf", "swaync/config.json", "swaync/style.css", "wofi/config", "wofi/style.css", "wlogout/layout", "wlogout/style.css", "starship.toml"]:
        import_text(".config/" + rel, "dot_config/" + rel)
    for path in sorted((HOME / ".config/micro/colorschemes").glob("catppuccin-*.micro")):
        import_text(str(path.relative_to(HOME)), "dot_config/micro/colorschemes/" + path.name)
    for src, dest in [(".bashrc", "dot_bashrc"), (".bash_profile", "dot_bash_profile"), (".zshrc", "dot_zshrc")]:
        transform = (lambda t: 'if [[ -r /usr/share/cachyos-zsh-config/cachyos-config.zsh ]]; then\n' + t + '\nfi\n') if src == '.zshrc' else None
        import_text(src, dest, transform)
    base = "repos/waybarcfgs/minimal-waybar/waybar/"
    active = (HOME / base / "config-simple").read_text()
    check_text(active, "Waybar ativo")
    active = active.replace(str(HOME) + "/" + base.rstrip("/"), "__HOME__/.config/waybar")
    bar = jsonc(active)
    bar["hyprland/language"]["on-click"] = "hyprctl switchxkblayout all next"
    bar["pulseaudio#mic"]["on-click"] = "pactl set-source-mute @DEFAULT_SOURCE@ toggle"
    json_write("inventory/waybar.json", bar)
    for src, dest in [("style-simple.css", "style.css"), ("power-style.css", "power-style.css"), ("power-layout", "power-layout")]:
        import_text(base + src, "dot_config/waybar/" + dest, lambda t: t.replace(str(HOME) + "/" + base.rstrip("/"), str(HOME) + "/.config/waybar"))
    for name in ["main.css", "dark.css", "light.css", "material-dark.css"]:
        import_text(base + "themes/" + name, "dot_config/waybar/themes/" + name)
    for name in ["brightness-set.sh", "brightness-slider.sh", "power-profile.sh"]:
        import_text(base + "scripts/" + name, "dot_config/waybar/scripts/executable_" + name)
    # Inactive configurations are retained as reference, never deployed by default.
    for rel in ["alacritty/alacritty.toml", "wezterm/wezterm.lua", "waybar/config.jsonc", "waybar/style.css", "waybar/power_profiles_menu.xml"]:
        path = HOME / ".config" / rel
        if path.is_file():
            text = path.read_text().replace(str(HOME), "$HOME")
            write("reference/inactive/" + rel, text)
    for src in [".config/hypr/wallpapers/wallpaper.jpg", ".config/wallpapers/wallpaper.jpg"]:
        path = HOME / src
        if path.is_file():
            dest = "chezmoi/dot_config/hypr/wallpapers/wallpaper.jpg" if "/hypr/" in src else "reference/inactive/wallpaper.jpg"
            write(dest, strip_jpeg_metadata(path.read_bytes()))
    print("Configurações: allowlist importada; EXIF/XMP/IPTC removidos dos wallpapers; nenhum perfil de aplicação importado.")


if __name__ == "__main__":
    if len(__import__('sys').argv) != 2 or __import__('sys').argv[1] != "--capture-approved":
        raise SystemExit("Uso explícito, somente uma vez: python3 scripts/capture.py --capture-approved")
    capture_packages()
    capture_configs()
    capture_prompt_settings()
