#!/usr/bin/env python3
"""Recover only this setup's recorded files. Default: read-only recovery plan."""
import argparse
import hashlib
import json
import os
import sys
import tempfile
from pathlib import Path

from setup import read_json, reject_symlinks, destination_path
from safety import check_text


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def recovery_plan(manifest_path, destination):
    manifest_path, destination = destination_path(manifest_path), destination_path(destination)
    data = read_json(manifest_path)
    if data.get("version") != 1 or data.get("destination") != str(destination.resolve()):
        raise ValueError("Versão/destino não corresponde ao backup; informe o destino original")
    actions = []
    for entry in data["files"]:
        name = entry["path"]
        if Path(name).is_absolute() or ".." in Path(name).parts:
            raise ValueError("Caminho inválido no manifesto")
        path = reject_symlinks(destination, name)
        if path.exists() and not path.is_file(): raise ValueError(f"Destino não regular: {name}")
        if not entry["previously_existed"] and not path.exists(): continue
        current = digest(path) if path.exists() else None
        current_mode = path.stat().st_mode & 0o777 if path.exists() else None
        if entry["previously_existed"] and current == entry["previous_sha256"] and current_mode == entry["previous_mode"]:
            continue
        if current != entry["applied_sha256"] or current_mode != entry["applied_mode"]:
            raise ValueError(f"Arquivo alterado posteriormente; recuperação interrompida sem descartar seu trabalho: {name}")
        action = {"path": name, "current_sha256": current, "current_mode": current_mode, "restore": entry["previously_existed"]}
        if action["restore"]:
            source = reject_symlinks(manifest_path.parent, name)
            if not source.is_file() or digest(source) != entry["previous_sha256"]:
                raise ValueError(f"Backup ausente ou divergente: {name}")
            content = source.read_bytes()
            if source.suffix.lower() not in {".jpg", ".png"}: check_text(content.decode(), name)
            action.update(content=content, mode=entry["previous_mode"])
        actions.append(action)
    return actions


def recover(actions, destination):
    for action in actions:
        path = reject_symlinks(destination, action["path"])
        if not path.is_file() or digest(path) != action["current_sha256"] or path.stat().st_mode & 0o777 != action["current_mode"]:
            raise ValueError("Arquivo mudou após planejar recuperação; operação interrompida")
        if not action["restore"]:
            # Only files created by us, with exactly our recorded content.
            path.unlink()
            continue
        with tempfile.NamedTemporaryFile(dir=path.parent, prefix=".recover-", delete=False) as stream:
            temporary = Path(stream.name)
            try:
                stream.write(action["content"])
                stream.flush()
                os.fsync(stream.fileno())
                temporary.chmod(action["mode"])
                os.replace(temporary, path)
            finally:
                if temporary.exists(): temporary.unlink()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", required=True)
    parser.add_argument("--destination", default=str(Path.home()))
    parser.add_argument("--apply", action="store_true")
    args = parser.parse_args()
    actions = recovery_plan(args.manifest, args.destination)
    for action in actions:
        print(("RESTAURAR: " if action["restore"] else "REMOVER arquivo criado pelo setup: ") + action["path"])
    if args.apply:
        if os.geteuid() == 0: raise ValueError("Não execute recuperação como root")
        recover(actions, args.destination)
    print(f"{len(actions)} operações; " + ("recuperação concluída" if args.apply else "somente planejamento, nada alterado"))


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, KeyError, json.JSONDecodeError) as exc:
        print("ERRO: " + str(exc), file=sys.stderr)
        raise SystemExit(2)
