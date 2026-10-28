"""Conservative export checks. Findings contain paths/rules, NEVER matched values."""
import re
from pathlib import Path

RULES = {
    "private-key": re.compile(r"-----BEGIN (?:[A-Z0-9 ]+ )?PRIVATE KEY-----"),
    "known-token": re.compile(r"\b(?:gh[pousr]_[A-Za-z0-9]{20,}|github_pat_[A-Za-z0-9_]{30,}|sk-(?:proj-)?[A-Za-z0-9_-]{24,}|AKIA[A-Z0-9]{16})\b"),
    "jwt": re.compile(r"\beyJ[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\.[A-Za-z0-9_-]{12,}\b"),
    "url-credentials": re.compile(r"[a-z][a-z0-9+.-]*://[^\s/@:]+:[^\s/@]+@", re.I),
    "literal-credential": re.compile(r'''(?im)^[\t ]*(?:export[\t ]+)?["']?(?:[\w-]*(?:api[_-]?key|access[_-]?token|refresh[_-]?token|auth[_-]?token|password|passwd|secret)[\w-]*)["']?[\t ]*[:=][\t ]*["']?([^\s"'#,;}]+)'''),
    "fish-credential": re.compile(r'''(?im)^[\t ]*set[\t ]+(?:-[\w-]+[\t ]+)*[\w-]*(?:TOKEN|PASSWORD|SECRET|API_KEY)[\w-]*[\t ]+["']?([^\s"']+)'''),
    "bearer-literal": re.compile(r"(?i)Bearer\s+[A-Za-z0-9_.-]{20,}"),
}
DENIED_NAMES = {"fish_variables", "auth.json", "hosts.yml", "known_hosts", ".netrc", ".git-credentials", "chezmoistate.boltdb", "cookies", "cookies.sqlite"}
DENIED_DIRS = {".ssh", ".gnupg", ".aws", ".azure", ".kube", ".codex", ".android", ".pki", "keyrings", "kwalletd", "BraveSoftware", "chromium", "mozilla", ".mozilla", "google-chrome"}


def check_blob(data, relative):
    path = Path(relative)
    if path.name in DENIED_NAMES or set(path.parts) & DENIED_DIRS:
        return [f"{relative}: caminho privado proibido"]
    if path.suffix.lower() in {".jpg", ".jpeg", ".png"}:
        if not data.startswith((b"\xff\xd8\xff", b"\x89PNG\r\n\x1a\n")):
            return [f"{relative}: assinatura de imagem inválida"]
        return [f"{relative}: {rule}" for rule in findings(data.decode("latin-1"))]
    try:
        text = data.decode()
    except UnicodeDecodeError:
        return [f"{relative}: binário não autorizado"]
    return [f"{relative}: {rule}" for rule in findings(text)]


def findings(text):
    result = []
    for rule, pattern in RULES.items():
        for match in pattern.finditer(text):
            if rule in {"literal-credential", "fish-credential"}:
                value = match.group(1).lower()
                if value in {"true", "false", "none", "null", "", "0", "1"} or value.startswith(("$", "{env:", "{file:", "<")):
                    continue
            result.append(rule)
    return sorted(set(result))


def check_text(text, label):
    problems = findings(text)
    if problems:
        raise ValueError(f"Exportação bloqueada: {label}: {','.join(problems)} (valores omitidos)")


def check_tree(root):
    errors = []
    for path in sorted(Path(root).rglob("*")):
        relative = path.relative_to(root)
        if any(p in {".git", ".state", ".venv", "__pycache__"} for p in relative.parts):
            continue
        if path.is_symlink():
            errors.append(f"{relative}: symlink não permitido na fonte")
        elif path.is_file():
            errors.extend(check_blob(path.read_bytes(), relative))
    return errors
