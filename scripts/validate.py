#!/usr/bin/env python3
"""Validate without provisioning. Optional tools run only when already available."""
import argparse
import ast
import json
import os
import posixpath
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from safety import check_tree, check_blob

ROOT = Path(__file__).resolve().parents[1]
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "LC_ALL": "C.UTF-8", "LANG": "C.UTF-8"}


def run(args, *, env=None, capture=False):
    process = subprocess.run(args, cwd=ROOT, env=env or ENV, capture_output=capture, text=True)
    if process.returncode:
        raise ValueError(f"Validação falhou: {Path(args[0]).name} (código {process.returncode})")
    return process


def scan_secrets():
    errors = check_tree(ROOT)
    if shutil.which("git") and (ROOT / ".git").exists():
        # Scan ACTUAL index blobs too, not only the working tree.
        def git(*args):
            result = subprocess.run(["git", "-c", "core.fsmonitor=false", *args], cwd=ROOT, capture_output=True, env={**ENV, "GIT_OPTIONAL_LOCKS": "0"})
            if result.returncode: raise ValueError("Não foi possível inspecionar o índice Git com segurança")
            return result.stdout
        for row in git("ls-files", "--stage", "-z").split(b"\0"):
            if not row: continue
            meta, name = row.split(b"\t", 1)
            mode, oid, stage = meta.split()
            name = name.decode()
            if mode not in {b"100644", b"100755"} or stage != b"0" or set(Path(name).parts) & {".state", ".venv", "__pycache__"}:
                errors.append(name + ": entrada de índice proibida")
                continue
            errors.extend(check_blob(git("cat-file", "blob", oid.decode()), name))
    if errors: raise ValueError("\n".join(errors))
    print("PASS: fonte e índice Git (quando disponível), sem padrões bloqueados; verificação heurística, não garantia absoluta")


def syntax():
    count = 0
    for folder in ["scripts", "tests"]:
        for path in (ROOT / folder).glob("*.py"):
            ast.parse(path.read_text(), filename=str(path.relative_to(ROOT)))
            count += 1
    print(f"PASS: sintaxe Python ({count} arquivos; sem bytecode)")
    yaml_files = [ROOT / ".yamllint.yml", *ROOT.glob("ansible/**/*.yml"), *ROOT.glob("inventory/*.yml"), *ROOT.glob("profiles/*.yml")]
    try:
        import yaml
    except ImportError:
        print("SKIP: PyYAML ausente; use --isolated para YAML/Ansible/ShellCheck sem instalar no host")
    else:
        for path in yaml_files:
            list(yaml.safe_load_all(path.read_text()))
        print(f"PASS: YAML ({len(yaml_files)} arquivos)")
    if shutil.which("yamllint"):
        run(["yamllint", "--strict", *map(str, yaml_files)])
    paths = [ROOT / "bootstrap.sh", ROOT / "hooks/pre-commit"]
    paths.extend((ROOT / "chezmoi/dot_config/hypr/scripts").glob("*.sh"))
    paths.extend((ROOT / "chezmoi/dot_config/waybar/scripts").glob("*.sh"))
    shell = []
    for path in paths:
        text = path.read_text()
        if "python" in text.splitlines()[0]:
            ast.parse(text, filename=str(path))
        else:
            run(["bash", "-n", str(path)], capture=True)
            shell.append(str(path))
    print(f"PASS: sintaxe Shell ({len(shell)} arquivos ativos)")
    if shutil.which("shellcheck"):
        process = subprocess.run(["shellcheck", "--format=json", "--severity=warning", *shell], cwd=ROOT, env=ENV, capture_output=True, text=True)
        if process.returncode:
            for item in json.loads(process.stdout or "[]"):
                print(f"{Path(item['file']).relative_to(ROOT)}:{item['line']}:SC{item['code']} {item['level']}")
            raise ValueError("ShellCheck encontrou problemas (conteúdo de linhas omitido)")
        print("PASS: ShellCheck (warning/error; não executa scripts)")
    else:
        print("SKIP: ShellCheck ausente no host")


def validate_resources(files, destination):
    for name, item in files.items():
        if not name.startswith((".config/hypr/", ".config/waybar/", ".config/swaync/", ".config/wlogout/")) or name.endswith((".jpg", ".png")): continue
        text = item["content"].decode()
        if name.endswith(".css"):
            for reference in re.findall(r'''@import\s+(?:url\(\s*)?["']([^"']+)["']''', text):
                if "://" in reference or reference.startswith("/"): continue
                target = posixpath.normpath(posixpath.join(posixpath.dirname(name), reference))
                if target not in files:
                    raise ValueError(f"Recurso CSS ausente: {name} -> {reference}")
        for reference in re.findall(re.escape(str(destination)) + r'''/([^\s"';)]+\.(?:sh|conf|css|jsonc|jpg))''', text):
            if reference not in files:
                raise ValueError(f"Recurso gerenciado ausente: {name} -> {reference}")


def rendered_syntax():
    if not shutil.which("chezmoi"):
        print("SKIP: Chezmoi ausente neste ambiente")
        return
    import setup
    with tempfile.TemporaryDirectory(prefix="portable-validate-", dir="/tmp/opencode" if Path("/tmp/opencode").is_dir() else None) as tmp:
        data = setup.build_plan(setup.arguments(["--destination", tmp + "/home"]))["portable"]
        files = setup.render(Path(tmp) / "work", Path(tmp) / "home", data)
        validate_resources(files, Path(tmp) / "home")
        checked = {"node": 0, "fish": 0, "zsh": 0, "json": 0}
        for name, item in files.items():
            if name.endswith((".jpg", ".png")): continue
            path = Path(tmp) / "syntax" / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(item["content"])
            if path.suffix in {".cjs", ".mjs"} and shutil.which("node"):
                run(["node", "--check", str(path)], capture=True)
                checked["node"] += 1
            elif path.suffix == ".fish" and shutil.which("fish"):
                run(["fish", "--no-config", "-n", str(path)], capture=True)
                checked["fish"] += 1
            elif name == ".zshrc" and shutil.which("zsh"):
                run(["zsh", "-f", "-n", str(path)], capture=True)
                checked["zsh"] += 1
            if path.suffix == ".json" or name == ".config/waybar/config.jsonc":
                json.loads(item["content"])
                checked["json"] += 1
        print(f"PASS: templates/recursos isolados ({len(files)} arquivos); sintaxe disponível: {checked}")


def ansible_simulation():
    """Check the REAL roles against a fake pacman in a disposable container only."""
    if not shutil.which("ansible-playbook"): raise ValueError("Ansible ausente no ambiente de validação")
    with tempfile.TemporaryDirectory(prefix="ansible-fixture-") as tmp:
        work = Path(tmp)
        fake = work / "bin/pacman"
        fake.parent.mkdir()
        fake.write_text('#!/usr/bin/env python3\nimport os,sys\nfrom pathlib import Path\np=Path(os.environ["FIXTURE_PACKAGES"])\nargs=sys.argv[1:]\nif args==["-Qq"]: print(p.read_text() if p.exists() else "",end="")\nelif args[:1]==["-S"]:\n names=args[args.index("--")+1:]\n old=set(p.read_text().split()) if p.exists() else set()\n p.write_text("\\n".join(sorted(old|set(names)))+"\\n")\nelse: sys.exit(99)\n')
        fake.chmod(0o755)
        packages = work / "packages"
        packages.write_text("existing\n")
        variables = work / "vars.json"
        variables.write_text(json.dumps({"setup_packages": ["existing", "missing"], "setup_services": []}))
        env = {**ENV, "HOME": str(work), "PATH": str(fake.parent) + os.pathsep + os.environ["PATH"], "FIXTURE_PACKAGES": str(packages), "ANSIBLE_CONFIG": str(ROOT / "ansible/ansible.cfg"), "ANSIBLE_HOME": str(work / "ansible-home"), "ANSIBLE_LOCAL_TEMP": str(work / "ansible-local"), "ANSIBLE_REMOTE_TEMP": str(work / "ansible-remote"), "ANSIBLE_ROLES_PATH": str(ROOT / "ansible/roles"), "ANSIBLE_NOCOLOR": "1"}
        args = ["ansible-playbook", "-i", "localhost,", "-c", "local", str(ROOT / "ansible/playbooks/site.yml"), "-e", "@" + str(variables)]
        run([*args, "--syntax-check"], env=env)
        run([*args, "--check", "-e", '{"ansible_become":false}'], env=env)
        if packages.read_text() != "existing\n": raise ValueError("Check mode alterou fixture")
        run(args, env=env)
        if set(packages.read_text().split()) != {"existing", "missing"}: raise ValueError("Primeira execução divergente")
        second = run(args, env=env, capture=True)
        import re
        if not re.search(r"changed=0\s+", second.stdout): raise ValueError("Segunda execução não foi idempotente")
        print("PASS: Ansible syntax/check/idempotência do role de pacotes em fixture; serviços apenas syntax, NÃO é Arch/systemd real")


def isolated():
    if not shutil.which("docker"): raise ValueError("Docker ausente; nenhuma instalação automática")
    image = "python:3.13-slim"
    probe = subprocess.run(["docker", "image", "inspect", "--format", "{{.Id}}", image], capture_output=True, text=True)
    if probe.returncode: raise ValueError("Imagem python:3.13-slim não está em cache; nenhum pull automático")
    code = ('import os,subprocess,sys; '
            'subprocess.run([sys.executable,"-m","pip","install","--quiet","--root-user-action=ignore","--disable-pip-version-check","--no-cache-dir","--target","/tmp/deps","-r","/work/tests/requirements.txt"],check=True); '
            'env={**os.environ,"PYTHONPATH":"/tmp/deps","PATH":"/tmp/deps/bin:"+os.environ["PATH"],"HOME":"/tmp/home","ANSIBLE_HOME":"/tmp/ansible-home","ANSIBLE_LOCAL_TEMP":"/tmp/ansible-local","PYTHONDONTWRITEBYTECODE":"1"}; '
            'sys.exit(subprocess.run([sys.executable,"-B","scripts/validate.py","--container"],env=env).returncode)')
    run(["docker", "run", "--rm", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges", "--pids-limit", "256", "--memory", "2g", "--cpus", "2", "--tmpfs", "/tmp:rw,exec,nosuid,nodev,size=1g", "--volume", str(ROOT) + ":/work:ro", "--workdir", "/work", probe.stdout.strip(), "python", "-B", "-c", code])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--secrets-only", action="store_true")
    parser.add_argument("--isolated", action="store_true", help="Container descartável; ferramentas instaladas somente no tmpfs do container")
    parser.add_argument("--container", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    scan_secrets()
    if args.secrets_only: return
    syntax()
    run([sys.executable, "-B", "-m", "unittest", "discover", "-s", "tests", "-v"])
    rendered_syntax()
    if args.container: ansible_simulation()
    if args.isolated: isolated()


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, SyntaxError) as exc:
        print("ERRO: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
