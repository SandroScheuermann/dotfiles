#!/usr/bin/env python3
"""Portable Arch setup. Default: a genuinely read-only plan, no cache/network."""
import argparse
import copy
import hashlib
import io
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from safety import check_text, check_tree

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_RE = re.compile(r"^[a-zA-Z0-9@_+.-]+$")
MINIMAL = {"core", "shell", "desktop"}
OVERRIDE_KEYS = {"profile", "monitors", "keyboard_layout", "keyboard_variant", "fingerprint", "suspend", "components_add", "components_remove", "packages_add", "packages_remove"}


def read_json(path):
    text = Path(path).read_text()
    check_text(text, Path(path).name)
    return json.loads(text)


def command(args, *, check=True):
    process = subprocess.run(args, capture_output=True, text=True, env={**os.environ, "LC_ALL": "C"})
    if check and process.returncode:
        raise RuntimeError(f"Consulta falhou: {args[0]} (código {process.returncode}); saída omitida por segurança")
    return process


def execute(args, **kwargs):
    result = subprocess.run(args, **kwargs)
    if result.returncode:
        raise RuntimeError(f"Execução falhou: {Path(args[0]).name} (código {result.returncode})")


def os_distribution():
    try:
        content = Path("/etc/os-release").read_text()
    except OSError:
        return "unsupported"
    pairs = dict(line.split("=", 1) for line in content.splitlines() if "=" in line)
    ident = pairs.get("ID", "").strip('"')
    like = pairs.get("ID_LIKE", "").strip('"').split()
    return "cachyos" if ident == "cachyos" else "arch" if ident == "arch" or "arch" in like else "unsupported"


def hardware():
    power = Path("/sys/class/power_supply")
    batteries = sorted(p.name for p in power.glob("*") if (p / "type").is_file() and (p / "type").read_text().strip() == "Battery")
    backlights = sorted(p.name for p in Path("/sys/class/backlight").glob("*"))
    try:
        chassis = int(Path("/sys/class/dmi/id/chassis_type").read_text().strip())
    except (OSError, ValueError):
        chassis = 0
    try:
        intel_cpu = "GenuineIntel" in Path("/proc/cpuinfo").read_text()
    except OSError:
        intel_cpu = False
    intel_gpu = False
    for dev in Path("/sys/bus/pci/devices").glob("*"):
        try:
            intel_gpu |= (dev / "class").read_text().strip().startswith("0x03") and (dev / "vendor").read_text().strip() == "0x8086"
        except OSError:
            pass
    return {"profile": "laptop" if batteries or chassis in {8, 9, 10, 14, 31, 32} else "desktop", "battery": batteries[0] if batteries else "", "backlight": backlights[0] if backlights else "", "intel_cpu": intel_cpu, "intel_gpu": bool(intel_gpu)}


def condition_met(condition, context):
    return {"always": True, "cachyos": context["distribution"] == "cachyos", "intel_cpu": context["hardware"]["intel_cpu"], "intel_gpu": context["hardware"]["intel_gpu"]}.get(condition, False)


def load_overrides(path):
    if not path:
        return {}
    data = read_json(path)
    if not isinstance(data, dict) or set(data) - OVERRIDE_KEYS:
        raise ValueError("Override inválido: use somente as chaves documentadas")
    for key in {"components_add", "components_remove", "packages_add", "packages_remove", "monitors"}:
        if key in data and (not isinstance(data[key], list) or not all(isinstance(v, str) for v in data[key])):
            raise ValueError(f"Override inválido: {key} deve ser lista de strings")
    for key in {"fingerprint", "suspend"}:
        if key in data and type(data[key]) is not bool:
            raise ValueError(f"Override inválido: {key} deve ser booleano")
    for key in {"packages_add", "packages_remove"}:
        if any(not PACKAGE_RE.fullmatch(v) for v in data.get(key, [])):
            raise ValueError("Nome de pacote inválido no override")
    for key in {"keyboard_layout", "keyboard_variant"}:
        if key in data and (not isinstance(data[key], str) or not re.fullmatch(r"[a-zA-Z0-9_,()-]*", data[key])):
            raise ValueError("Layout/variante de teclado inválido")
    for monitor in data.get("monitors", []):
        if not re.fullmatch(r"[a-zA-Z0-9_.,:@+ /-]+", monitor):
            raise ValueError("Monitor inválido; não são permitidas diretivas ou quebras de linha")
    if "profile" in data and data["profile"] not in {"desktop", "laptop"}:
        raise ValueError("Perfil inválido no override")
    return data


def comma_set(value):
    return {x.strip() for x in value.split(",") if x.strip()}


def destination_path(value):
    path = Path(value).expanduser().absolute()
    if any(part.is_symlink() for part in (path, *path.parents)):
        raise ValueError("Destino ou ancestral é symlink; use um diretório real")
    return path.resolve()


def build_plan(args, *, detected=None, distribution=None):
    manifest = read_json(ROOT / "inventory/packages.yml")
    detected = hardware() if detected is None else detected
    distribution = os_distribution() if distribution is None else distribution
    overrides = load_overrides(args.overrides)
    profile = overrides.get("profile", detected["profile"]) if args.profile == "auto" else args.profile
    config = read_json(ROOT / f"profiles/{profile}.yml")
    config.update({k: v for k, v in overrides.items() if k in config})
    config["profile"] = profile
    all_components = {p["component"] for p in manifest["packages"]}
    components = set(MINIMAL if args.preset == "minimal" else all_components - {"boot"})
    components |= set(overrides.get("components_add", [])) | comma_set(args.with_components)
    components -= set(overrides.get("components_remove", [])) | comma_set(args.without)
    if components - all_components:
        raise ValueError("Componente desconhecido; consulte --list-components")
    for component, needed in {"desktop": {"core", "shell"}, "android": {"dev"}}.items():
        if component in components and needed - components:
            raise ValueError(f"Componente {component} exige: {', '.join(sorted(needed - components))}")
    if "boot" in components and not args.allow_boot:
        raise ValueError("Componente boot exige --allow-boot; não particiona nem instala bootloader")
    context = {"distribution": distribution, "hardware": detected}
    selected, deferred = [], []
    for entry in manifest["packages"]:
        if entry["component"] not in components:
            continue
        if not condition_met(entry["condition"], context):
            deferred.append({"name": entry["name"], "reason": entry["condition"]})
            continue
        if entry["name"] not in overrides.get("packages_remove", []):
            selected.append(dict(entry))
    for name in overrides.get("packages_add", []):
        if name in manifest["excluded"]:
            raise ValueError("Override tenta reintroduzir pacote explicitamente excluído")
        if not any(p["name"] == name for p in selected):
            selected.append({"name": name, "component": "override", "source": "repository", "condition": "always"})
    runtime = {
        "core": {"git", "neovim", "yazi"},
        "shell": {"kitty", "fish", "starship", "zoxide"},
        "desktop": {"hyprland", "waybar", "hyprlauncher", "hyprlock", "hypridle", "hyprpaper", "hyprshot", "hyprsunset", "jq", "qt6-wayland", "cliphist", "wl-clipboard", "libnotify", "grim", "slurp", "swaync", "wlogout", "brightnessctl", "power-profiles-daemon", "playerctl", "pipewire", "wireplumber", "ttf-jetbrains-mono-nerd"},
    }
    for required, component in [(name, group) for group, names in runtime.items() for name in sorted(names)]:
        if component in components and not any(p["name"] == required for p in selected):
            raise ValueError(f"Override quebra componente {component}: pacote necessário {required}")
    if any(not PACKAGE_RE.fullmatch(p["name"]) for p in selected):
        raise ValueError("Nome de pacote inválido no manifesto")
    installed = set(command(["pacman", "-Qq"], check=False).stdout.split()) if shutil.which("pacman") else set()
    # Batch local queries: never refresh, and avoid hundreds of pacman startups.
    repository_names = [p["name"] for p in selected if p["source"] == "repository"]
    available = None
    if shutil.which("pacman"):
        metadata = command(["pacman", "-Si", "--", *repository_names], check=False).stdout if repository_names else ""
        available = {line.split(":", 1)[1].strip() for line in metadata.splitlines() if ":" in line and line.split(":", 1)[0].strip() == "Name"}
    warnings, blockers = [], []
    for p in selected:
        p["installed"] = p["name"] in installed
        if p["source"] == "repository":
            p["available_cached"] = p["name"] in available if available is not None else None
            if p["available_cached"] is False:
                warnings.append(f"Sem metadados locais de repositório: {p['name']}")
            if not p["installed"] and p["available_cached"] is not True:
                blockers.append(f"Pacote sem disponibilidade local confirmada: {p['name']}")
        elif not p["installed"]:
            if p["source"] == "unresolved":
                blockers.append(f"Origem pendente: {p['name']}")
            elif not args.allow_aur:
                blockers.append(f"AUR não autorizado: {p['name']} (--allow-aur após revisar PKGBUILD)")
            elif not shutil.which("paru") and not any(item["name"] == "paru" and (item["name"] in installed or (available is not None and item["name"] in available)) for item in selected):
                blockers.append("AUR selecionado, mas paru não está instalado")
    manual = [t for t in read_json(ROOT / "inventory/manual.yml")["tools"] if t["component"] in components and t["resolution"] == "unresolved"]
    for tool in manual:
        tool["present"] = bool(shutil.which(tool["command"])) or any((Path.home() / relative).is_file() for relative in tool.get("relative_paths", []))
        warnings.append(f"Origem/procedimento manual não fixado: {tool['name']}")
        if not tool["present"]:
            blockers.append(f"Ferramenta manual ausente: {tool['name']}")
    services = []
    if args.services:
        for unit in read_json(ROOT / "inventory/services.yml")["services"]:
            if unit["component"] in components and condition_met(unit.get("condition", "always"), context):
                if unit["component"] == "cpu-intel" and not detected["intel_cpu"]:
                    continue
                services.append(unit)
    config.update({"home": str(destination_path(args.destination)), "core": "core" in components, "desktop": "desktop" in components, "shell": "shell" in components, "dev": "dev" in components, "obsidian": any(p["name"] == "obsidian" for p in selected), "battery": detected["battery"], "backlight": bool(detected["backlight"])})
    config["waybar"] = waybar(config, detected)
    if distribution == "unsupported":
        warnings.append("Sistema atual não é Arch-based; somente renderização isolada/planejamento disponíveis")
    if args.upgrade_system:
        warnings.append("Atualização completa do sistema explicitamente selecionada: pacman -Syu")
    return {"profile": profile, "preset": args.preset, "distribution": distribution, "components": sorted(components), "packages": sorted(selected, key=lambda p: p["name"]), "conditional_not_applicable": deferred, "services": services, "manual": manual, "warnings": sorted(set(warnings)), "blockers": sorted(set(blockers)), "portable": config}


def waybar(config, detected):
    data = read_json(ROOT / "inventory/waybar.json")
    def home(value):
        if isinstance(value, str): return value.replace("__HOME__", config["home"])
        if isinstance(value, list): return [home(v) for v in value]
        if isinstance(value, dict): return {k: home(v) for k, v in value.items()}
        return value
    data = home(data)
    if config["profile"] != "laptop" or not detected["battery"]:
        for key in ["modules-left", "modules-center", "modules-right"]:
            data[key] = [m for m in data.get(key, []) if m != "battery"]
        data.pop("battery", None)
    elif "battery" in data:
        data["battery"]["bat"] = detected["battery"]
        data["battery"].pop("adapter", None)
    if not detected["backlight"]:
        for key in ["modules-left", "modules-center", "modules-right"]:
            data[key] = [m for m in data.get(key, []) if m not in {"backlight", "custom/brightness-level"}]
        data.pop("backlight", None)
        data.pop("custom/brightness-level", None)
    elif "backlight" in data:
        data["backlight"]["device"] = detected["backlight"]
    if "temperature" in data:
        data["temperature"].pop("hwmon-path", None)
        data["temperature"].pop("thermal-zone", None)
    return data


def chezmoi_args(work, destination, data):
    work = Path(work)
    work.mkdir(parents=True, exist_ok=True)
    (work / "config.json").write_text("{}\n")
    (work / "data.json").write_text(json.dumps({"portable": data}))
    return ["chezmoi", "--source", str(ROOT / "chezmoi"), "--destination", str(destination), "--config", str(work / "config.json"), "--config-format", "json", "--override-data-file", str(work / "data.json"), "--persistent-state", str(work / "state.boltdb"), "--cache", str(work / "cache"), "--refresh-externals=never", "--no-tty", "--no-pager", "--color=false"]


def render(work, destination, data):
    result = subprocess.run(chezmoi_args(work, destination, data) + ["archive", "--format", "tar"], capture_output=True)
    if result.returncode:
        # Source templates are non-sensitive, but error values are still withheld.
        raise RuntimeError("Chezmoi não conseguiu renderizar; consulte validação de templates (saída omitida)")
    files = {}
    with tarfile.open(fileobj=io.BytesIO(result.stdout), mode="r:") as archive:
        for member in archive.getmembers():
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Caminho de archive inválido")
            if member.isdir(): continue
            if not member.isfile(): raise ValueError("Somente arquivos regulares são aceitos no archive")
            content = archive.extractfile(member).read()
            if path.suffix.lower() not in {".jpg", ".png"}:
                check_text(content.decode(), str(path))
            files[str(path)] = {"content": content, "mode": 0o755 if member.mode & 0o111 else 0o644}
    return files


def reject_symlinks(destination, relative):
    path = destination_path(destination)
    for part in Path(relative).parts:
        path /= part
        if path.is_symlink(): raise ValueError(f"Symlink no destino gerenciado: {relative}")
    return path


def changes(files, destination):
    result = []
    for name, entry in sorted(files.items()):
        path = reject_symlinks(destination, name)
        if name == ".config/hypr/local.conf" and path.exists(): continue
        if path.exists() and not path.is_file():
            raise ValueError(f"Destino não é arquivo regular: {name}")
        exists = path.exists()
        if exists and path.read_bytes() == entry["content"] and bool(path.stat().st_mode & 0o111) == bool(entry["mode"] & 0o111):
            continue
        if exists and path.suffix.lower() not in {".jpg", ".png"}:
            try: check_text(path.read_text(), name)
            except UnicodeDecodeError: raise ValueError(f"Arquivo existente não textual: {name}") from None
        result.append({"path": name, "exists": exists, "previous_sha256": hashlib.sha256(path.read_bytes()).hexdigest() if exists else None, "previous_mode": path.stat().st_mode & 0o777 if exists else None, **entry})
    return result


def apply_files(entries, destination, backup_dir):
    backup_dir = Path(backup_dir)
    manifest = []
    if entries:
        backup_dir.mkdir(parents=True, mode=0o700, exist_ok=False)
    for entry in entries:
        path = reject_symlinks(destination, entry["path"])
        if path.exists() != entry["exists"] or (entry["exists"] and (hashlib.sha256(path.read_bytes()).hexdigest() != entry["previous_sha256"] or path.stat().st_mode & 0o777 != entry["previous_mode"])):
            raise ValueError(f"Destino mudou após o planejamento; nada será sobrescrito: {entry['path']}")
        if entry["exists"]:
            backup = backup_dir / entry["path"]
            backup.parent.mkdir(parents=True, mode=0o700, exist_ok=True)
            shutil.copy2(path, backup)
        manifest.append({"path": entry["path"], "previously_existed": entry["exists"], "previous_sha256": entry["previous_sha256"], "previous_mode": entry["previous_mode"], "applied_sha256": hashlib.sha256(entry["content"]).hexdigest(), "applied_mode": entry["mode"]})
        manifest_path = backup_dir / "manifest.json"
        payload = json.dumps({"version": 1, "destination": str(Path(destination).resolve()), "files": manifest}, indent=2) + "\n"
        with tempfile.NamedTemporaryFile(dir=backup_dir, prefix=".manifest-", delete=False) as stream:
            temporary_manifest = Path(stream.name)
            try:
                stream.write(payload.encode())
                stream.flush()
                os.fsync(stream.fileno())
                temporary_manifest.chmod(0o600)
                os.replace(temporary_manifest, manifest_path)
            finally:
                if temporary_manifest.exists(): temporary_manifest.unlink()
        path.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".portable-", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(entry["content"])
                stream.flush()
                os.fsync(stream.fileno())
                temporary.chmod(entry["mode"])
                os.replace(temporary, path)
            finally:
                if temporary.exists(): temporary.unlink()


def run_ansible(plan, work, check=False):
    package_names = [p["name"] for p in plan["packages"] if p["source"] == "repository" and (p["installed"] or p.get("available_cached") is True)]
    variables = Path(work) / "ansible-vars.json"
    variables.write_text(json.dumps({"setup_packages": package_names, "setup_services": plan["services"]}))
    argv = ["ansible-playbook", "-i", "localhost,", "-c", "local", str(ROOT / "ansible/playbooks/site.yml"), "--extra-vars", "@" + str(variables)]
    if check:
        argv += ["--check", "--extra-vars", '{"ansible_become": false}']
    env = {**os.environ, "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8", "ANSIBLE_CONFIG": str(ROOT / "ansible/ansible.cfg"), "ANSIBLE_LOCAL_TEMP": str(Path(work) / "ansible-tmp"), "ANSIBLE_ROLES_PATH": str(ROOT / "ansible/roles"), "ANSIBLE_NOCOLOR": "1", "PYTHONDONTWRITEBYTECODE": "1"}
    execute(argv, env=env)


def show_plan(plan, args):
    if args.json:
        view = {k: v for k, v in plan.items() if k != "portable"}
        print(json.dumps(view, ensure_ascii=False, indent=2))
        return
    packages = plan["packages"]
    print(f"Plano somente leitura: {plan['distribution']} / {plan['profile']} / {plan['preset']}")
    print("Componentes: " + ", ".join(plan["components"]))
    print(f"Pacotes selecionados: {len(packages)}; já instalados: {sum(p['installed'] for p in packages)}; serviços opt-in: {len(plan['services'])}")
    print(f"Condicionais não aplicáveis: {len(plan['conditional_not_applicable'])}")
    for warning in plan["warnings"]: print("AVISO: " + warning)
    for blocker in plan["blockers"]: print("PENDÊNCIA: " + blocker)
    missing = [name for name in ["chezmoi", "ansible-playbook"] if not shutil.which(name)]
    if missing: print("Pré-requisitos ausentes: " + ", ".join(missing))
    if args.dry_run:
        print("Nenhum arquivo/cache foi criado; nenhuma rede, instalação, configuração ou serviço foi alterado.")
        print("Templates/diffs não executados no dry-run estrito; use validação isolada ou --check.")


def arguments(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Plano estritamente somente leitura (padrão)")
    mode.add_argument("--check", action="store_true", help="Ansible check + comparação de arquivos, sem aplicar")
    mode.add_argument("--apply", action="store_true", help="Autoriza aplicar no destino")
    parser.add_argument("--profile", choices=["auto", "desktop", "laptop"], default="auto")
    parser.add_argument("--preset", choices=["minimal", "full"], default="full")
    parser.add_argument("--with", dest="with_components", default="", help="Componentes adicionais separados por vírgula")
    parser.add_argument("--without", default="", help="Componentes omitidos separados por vírgula")
    parser.add_argument("--overrides", help="Arquivo JSON local; nunca contém segredos")
    parser.add_argument("--destination", default=str(Path.home()))
    parser.add_argument("--dotfiles-only", action="store_true")
    parser.add_argument("--packages-only", action="store_true")
    parser.add_argument("--services", action="store_true", help="Opt-in para unidades declaradas, sem desabilitar outras")
    parser.add_argument("--replace-existing", action="store_true", help="Autoriza conflitos após backup local")
    parser.add_argument("--allow-aur", action="store_true", help="Após revisão do PKGBUILD; mantém prompts do paru")
    parser.add_argument("--skip-unresolved", action="store_true", help="Permite restauração parcial claramente relatada")
    parser.add_argument("--allow-boot", action="store_true", help="Autoriza somente pacotes do módulo boot")
    parser.add_argument("--install-prerequisites", action="store_true", help="Somente com --apply: pacman sem refresh")
    parser.add_argument("--upgrade-system", action="store_true", help="Somente com --apply: atualização completa opt-in")
    parser.add_argument("--list-components", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    if not args.apply and not args.check: args.dry_run = True
    if args.dotfiles_only and args.packages_only: parser.error("--dotfiles-only e --packages-only são exclusivos")
    if args.dotfiles_only and args.services: parser.error("--dotfiles-only não aceita --services")
    if args.dotfiles_only and args.upgrade_system: parser.error("--dotfiles-only não aceita --upgrade-system")
    if (args.install_prerequisites or args.upgrade_system) and not args.apply: parser.error("Instalação/atualização exige --apply")
    return args


def main(argv=None):
    args = arguments(argv)
    if args.list_components:
        print("\n".join(sorted({p["component"] for p in read_json(ROOT / "inventory/packages.yml")["packages"]})))
        return 0
    plan = build_plan(args)
    show_plan(plan, args)
    if args.dry_run: return 0
    if os.geteuid() == 0: raise ValueError("Não execute bootstrap como root; sudo é solicitado somente em tarefas necessárias")
    if not args.dotfiles_only and (plan["distribution"] == "unsupported" or platform.machine() != "x86_64"):
        raise ValueError("Provisionamento suporta somente Arch-based x86_64")
    if Path(args.destination).expanduser().resolve() != Path.home().resolve() and not args.dotfiles_only:
        raise ValueError("Destino alternativo exige --dotfiles-only; pacotes/serviços pertencem ao sistema atual")
    if plan["blockers"] and not args.skip_unresolved and not args.dotfiles_only:
        raise ValueError("Reprodução incompleta bloqueada; resolva as pendências ou use --skip-unresolved conscientemente")
    problems = check_tree(ROOT)
    if problems: raise ValueError("Verificação de segredos/fonte bloqueou execução: " + "; ".join(problems))
    prerequisites = (["chezmoi"] if not args.packages_only else []) + ([] if args.dotfiles_only else ["ansible-playbook"])
    absent = [p for p in prerequisites if not shutil.which(p)]
    if absent:
        if not args.install_prerequisites:
            raise ValueError("Pré-requisitos ausentes; --check nunca os instala: " + ", ".join(absent))
        execute(["sudo", "pacman", "-S", "--needed", "--noconfirm", "--", "git", "python", "chezmoi", "ansible-core"])
    if args.services:
        display = Path("/etc/systemd/system/display-manager.service")
        if any(s["name"] == "sddm.service" for s in plan["services"]) and display.is_symlink() and display.resolve().name != "sddm.service":
            raise ValueError("Outro display manager configurado; não será substituído")
        if command(["systemctl", "is-active", "systemd-networkd.service"], check=False).returncode == 0:
            raise ValueError("systemd-networkd ativo; não iniciar NetworkManager automaticamente")
    state = ROOT / ".state"
    if state.is_symlink(): raise ValueError("Diretório de estado não pode ser symlink")
    state.mkdir(mode=0o700, exist_ok=True)
    state.chmod(0o700)
    with tempfile.TemporaryDirectory(prefix="operation-", dir=state) as tmp:
        work = Path(tmp)
        pending = []
        if not args.packages_only:
            files = render(work / "chezmoi", Path(args.destination).expanduser().resolve(), plan["portable"])
            pending = changes(files, Path(args.destination).expanduser().resolve())
            print(f"Chezmoi: {len(files)} arquivos renderizados; {len(pending)} alterações; valores/conteúdos não exibidos.")
            for p in pending: print(("CONFLITO: " if p["exists"] else "CRIAR: ") + p["path"])
            if args.apply and any(p["exists"] for p in pending) and not args.replace_existing:
                raise ValueError("Conflitos detectados ANTES do provisionamento. Requer --replace-existing para backup e substituição")
        if args.check:
            if not args.dotfiles_only: run_ansible(plan, work, check=True)
            print("Check concluído; destino e sistema não foram alterados.")
            return 0
        if args.upgrade_system:
            execute(["sudo", "pacman", "-Syu"])
        if not args.dotfiles_only:
            execute(["sudo", "-v"])
            run_ansible(plan, work)
            aur = [p["name"] for p in plan["packages"] if p["source"] == "aur" and not p["installed"]]
            if aur and args.allow_aur and shutil.which("paru"):
                execute(["paru", "-S", "--needed", "--", *aur])
        if not args.packages_only:
            backup = state / "backups" / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
            apply_files(pending, Path(args.destination).expanduser().resolve(), backup)
            print(f"Arquivos aplicados: {len(pending)}. Backups/manifesto locais em .state/backups/ quando houve alterações.")
        if plan["blockers"]: print("Restauração PARCIAL: pendências do plano continuam não resolvidas.")
        print("Concluído. Nenhuma limpeza/desinstalação solicitada pelo bootstrap; nenhum push executado.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as exc:
        print("ERRO: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
