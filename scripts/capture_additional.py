#!/usr/bin/env python3
"""Explicitly scoped application code/settings, not auth/session data."""
import json
from pathlib import Path
from capture import HOME, ROOT, write, json_write, query
from safety import check_text, findings, DENIED_NAMES, RULES


def copy_code(source, relative):
    if source.is_symlink() or not source.is_file() or source.name in DENIED_NAMES:
        return False
    text = source.read_text()
    if relative == "gsd-core/references/verification-patterns.md":
        # Documentation examples are not credentials to preserve. Replace values
        # in memory before ANY export; never print or persist their originals.
        def redact(match):
            start, end = match.span(1)
            return match.group(0)[:start - match.start()] + "<LOCAL_ONLY>" + match.group(0)[end - match.start():]
        text = RULES["literal-credential"].sub(redact, text)
    check_text(text, relative)
    # Preserve literal template syntax in GSD Markdown; only HOME is substituted.
    text = text.replace("{{", '{{ "{{" }}').replace(str(HOME), "{{ .portable.home }}")
    if source.stat().st_mode & 0o111:
        path = Path(relative)
        relative = str(path.with_name("executable_" + path.name))
    write("chezmoi/dot_config/opencode/" + relative + ".tmpl", text)
    return True


def main():
    deferred = []
    count = 0
    config = HOME / ".config/opencode/opencode.jsonc"
    if config.is_file():
        text = config.read_text()
        check_text(text, "opencode.jsonc")
        write("chezmoi/dot_config/opencode/opencode.jsonc", text)
        count += 1
    old = HOME / "dotfiles-chezmoi/dot_config/opencode"
    candidates = []
    for part in ["plugins", "skills"]:
        for path in sorted((old / part).rglob("*")):
            if not path.is_file(): continue
            relative = path.relative_to(old)
            live = HOME / ".config/opencode" / relative
            candidates.append((live if live.is_file() and not live.is_symlink() else path, str(relative)))
    core = HOME / ".config/opencode/gsd-core"
    for part in ["bin", "contexts", "references", "templates", "workflows"]:
        for path in sorted((core / part).rglob("*")):
            if path.is_file() and path.suffix in {".cjs", ".json", ".md", ".sh"}:
                candidates.append((path, "gsd-core/" + str(path.relative_to(core))))
    for name in ["VERSION", "package.json", "bin/gsd_run"]:
        if (core / name).is_file(): candidates.append((core / name, "gsd-core/" + name))
    for source, relative in candidates:
        try:
            if copy_code(source, relative): count += 1
        except (ValueError, UnicodeError):
            deferred.append({"path": relative, "reason": "Revisão adicional de conteúdo exigida; nenhum valor exportado"})
    json_write("inventory/deferred-configs.json", {"deferred": deferred, "redacted_documentation": ["gsd-core/references/verification-patterns.md: credential example assignments replaced with <LOCAL_ONLY> before export"], "generated_not_copied": ["Bun generated completions (recreate from bun)", "raw fish_variables", "application profiles/auth/session state"], "opencode_plugins": "Current @latest plugin references preserved. No plugin executed or downloaded; no exact npm lockfile captured."})
    # Record enabled unit names only; never export generated units, environment or logs.
    snapshots = {}
    for scope, option in [("system", []), ("user", ["--user"])]:
        text = query("systemctl", *option, "list-unit-files", "--state=enabled,enabled-runtime", "--no-pager", "--no-legend")
        snapshots[scope] = [line.split()[0] for line in text.splitlines() if line.split() and "." in line.split()[0]]
    snapshots["not_auto_repaired"] = ["Twingate failed autostart", "stale Ly symlink"]
    json_write("inventory/enabled-units.json", snapshots)
    for source, target in [(HOME / ".config/hypr/scripts/wezterm-wayland-clipboard.sh", "reference/inactive/wezterm-wayland-clipboard.sh"), (HOME / "repos/waybarcfgs/minimal-waybar/waybar/scripts/weather.sh", "reference/inactive/weather.sh"), (Path("/usr/local/bin/remove-nvidia"), "reference/inactive/remove-nvidia.sh")]:
        if source.is_file() and not source.is_symlink():
            write(target, source.read_text().replace(str(HOME), "$HOME"))
    print(f"OpenCode/GSD: {count} arquivos de código/config revisados; {len(deferred)} pendências. Nenhuma autenticação incluída.")


if __name__ == "__main__":
    if __import__('sys').argv[1:] != ["--capture-approved"]:
        raise SystemExit("Uso explícito: python3 scripts/capture_additional.py --capture-approved")
    main()
