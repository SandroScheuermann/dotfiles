"""No provisioning: mocked package queries and disposable filesystem targets."""
import contextlib
import copy
import hashlib
import io
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import setup
import safety
import recover
import capture
import validate

HW = {"profile": "laptop", "battery": "BAT9", "backlight": "test_backlight", "intel_cpu": True, "intel_gpu": True}
MANIFEST = json.loads((ROOT / "inventory/packages.yml").read_text())
NAMES = {p["name"] for p in MANIFEST["packages"]}


def plan(argv=(), *, hardware=None, distribution="cachyos", installed=None, missing_commands=()):
    installed = NAMES if installed is None else installed
    def query(args, **kwargs):
        if args[1] == "-Qq":
            text = "\n".join(sorted(installed))
        else:
            text = "\n".join("Name : " + name for name in args[3:])
        return subprocess.CompletedProcess(args, 0, text, "")
    with mock.patch.object(setup, "command", side_effect=query), mock.patch.object(setup.shutil, "which", side_effect=lambda name: None if name in missing_commands else "/test/" + name):
        return setup.build_plan(setup.arguments(list(argv)), detected=hardware or HW, distribution=distribution)


class PlanTests(unittest.TestCase):
    def test_default_read_only(self):
        self.assertTrue(setup.arguments([]).dry_run)
        self.assertFalse(setup.arguments([]).apply)

    def test_exclusions_are_preserved(self):
        self.assertFalse({p["name"] for p in plan()["packages"]} & set(MANIFEST["excluded"]))
        self.assertIn("spotify_player", MANIFEST["excluded_manual"])

    def test_everything_accounted_for(self):
        snapshot = json.loads((ROOT / "inventory/installed.json").read_text())
        rows = snapshot["packages"] if isinstance(snapshot, dict) else snapshot
        explicit = {p["name"] for p in rows if p["reason"] == "explicit"}
        self.assertEqual(explicit - set(MANIFEST["excluded"]) - NAMES, set())

    def test_minimal_is_smaller(self):
        minimal = plan(["--preset", "minimal"])
        self.assertLess(len(minimal["packages"]), len(plan()["packages"]))
        self.assertFalse(minimal["portable"]["dev"])
        self.assertFalse(minimal["portable"]["obsidian"])

    def test_no_services_by_default(self):
        self.assertEqual(plan()["services"], [])

    def test_no_sshd_or_firewall_start(self):
        services = plan(["--services"])["services"]
        self.assertNotIn("sshd.service", {p["name"] for p in services})
        firewall = next(p for p in services if p["name"] == "ufw.service")
        self.assertTrue(firewall["enable_only"])

    def test_no_boot_without_both_flags(self):
        self.assertNotIn("boot", plan()["components"])
        with self.assertRaises(ValueError): plan(["--with", "boot"])
        self.assertIn("boot", plan(["--with", "boot", "--allow-boot"])["components"])

    def test_arch_skips_vendor_packages(self):
        arch = plan(distribution="arch")
        self.assertFalse(any(p["condition"] == "cachyos" for p in arch["packages"]))

    def test_non_intel_skips_intel(self):
        hw = {**HW, "intel_cpu": False, "intel_gpu": False}
        self.assertFalse(any(p["condition"].startswith("intel_") for p in plan(hardware=hw)["packages"]))

    def test_explicit_profile(self):
        self.assertEqual(plan(["--profile", "desktop"])["profile"], "desktop")

    def test_desktop_has_no_battery_or_backlight(self):
        hw = {**HW, "profile": "desktop", "battery": "", "backlight": ""}
        data = plan(hardware=hw)["portable"]
        self.assertNotIn("battery", data["waybar"])
        self.assertNotIn("backlight", data["waybar"])
        self.assertFalse(data["suspend"])

    def test_battery_name_is_detected_not_copied(self):
        self.assertEqual(plan()["portable"]["waybar"]["battery"]["bat"], "BAT9")

    def test_new_machine_reports_unknown_sources(self):
        data = plan(installed=set())
        self.assertTrue(any("slack-desktop-wayland" in b for b in data["blockers"]))
        self.assertTrue(any("AUR" in b for b in data["blockers"]))

    def test_aur_is_separate_opt_in(self):
        data = plan(["--allow-aur"], installed=set())
        self.assertFalse(any("AUR não autorizado" in b for b in data["blockers"]))
        self.assertTrue(any("slack-desktop-wayland" in b for b in data["blockers"]))

    def test_aur_helper_can_be_installed_by_selected_repository_module(self):
        data = plan(["--allow-aur"], installed=set(), missing_commands=["paru"])
        self.assertFalse(any("paru não está instalado" in b for b in data["blockers"]))

    def test_component_dependency_guard(self):
        with self.assertRaises(ValueError): plan(["--without", "shell"])
        with self.assertRaises(ValueError): plan(["--without", "dev"])

    def test_unknown_component(self):
        with self.assertRaises(ValueError): plan(["--with", "not-a-component"])

    def test_overrides_validation(self):
        for data in [{"unsupported": True}, {"suspend": "yes"}, {"packages_add": ["-bad;echo"]}, {"monitors": ["eDP-1\nexec=bad"]}, {"keyboard_layout": "us;bad"}]:
            with self.subTest(data=data), tempfile.TemporaryDirectory() as tmp:
                file = Path(tmp) / "override.json"
                file.write_text(json.dumps(data))
                with self.assertRaises(ValueError): setup.load_overrides(file)

    def test_override_cannot_reintroduce_exclusion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "override.json"
            path.write_text(json.dumps({"packages_add": ["steam"]}))
            with self.assertRaises(ValueError): plan(["--overrides", str(path)])

    def test_override_cannot_break_runtime(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "override.json"
            path.write_text(json.dumps({"packages_remove": ["hyprpaper"]}))
            with self.assertRaises(ValueError): plan(["--overrides", str(path)])

    def test_cli_profile_beats_override(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "override.json"
            path.write_text(json.dumps({"profile": "desktop"}))
            self.assertEqual(plan(["--overrides", str(path), "--profile", "laptop"])["profile"], "laptop")

    def test_preview_rejects_install_flags(self):
        for args in [["--install-prerequisites"], ["--upgrade-system"], ["--dotfiles-only", "--services"], ["--dotfiles-only", "--packages-only"], ["--apply", "--dotfiles-only", "--upgrade-system"]]:
            with contextlib.redirect_stderr(io.StringIO()), self.assertRaises(SystemExit): setup.arguments(args)


class FileTests(unittest.TestCase):
    def test_recover_permission_only_change(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest, backup = Path(tmp) / "home", Path(tmp) / "backup"
            dest.mkdir()
            path = dest / "file"
            path.write_text("same content")
            path.chmod(0o600)
            setup.apply_files(setup.changes({"file": {"content": b"same content", "mode": 0o755}}, dest), dest, backup)
            recover.recover(recover.recovery_plan(backup / "manifest.json", dest), dest)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_recovery_preserves_post_apply_permissions(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest, backup = Path(tmp) / "home", Path(tmp) / "backup"
            dest.mkdir()
            setup.apply_files(setup.changes({"file": {"content": b"ours", "mode": 0o644}}, dest), dest, backup)
            (dest / "file").chmod(0o400)
            with self.assertRaises(ValueError): recover.recovery_plan(backup / "manifest.json", dest)

    def test_apply_then_no_change_then_recover(self):
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            dest, backup = base / "home", base / "backup"
            dest.mkdir()
            (dest / "existing").write_text("old\n")
            files = {"existing": {"content": b"new\n", "mode": 0o644}, "created": {"content": b"created\n", "mode": 0o755}}
            pending = setup.changes(files, dest)
            setup.apply_files(pending, dest, backup)
            self.assertEqual(setup.changes(files, dest), [])
            self.assertEqual((backup / "existing").read_text(), "old\n")
            self.assertEqual((backup / "manifest.json").stat().st_mode & 0o777, 0o600)
            actions = recover.recovery_plan(backup / "manifest.json", dest)
            recover.recover(actions, dest)
            self.assertEqual((dest / "existing").read_text(), "old\n")
            self.assertFalse((dest / "created").exists())
            self.assertEqual(recover.recovery_plan(backup / "manifest.json", dest), [])

    def test_preserve_manual_local_conf(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            path = dest / ".config/hypr/local.conf"
            path.parent.mkdir(parents=True)
            path.write_text("my override\n")
            self.assertEqual(setup.changes({".config/hypr/local.conf": {"content": b"default", "mode": 0o644}}, dest), [])

    def test_symlink_guard(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp)
            (dest / "real").mkdir()
            (dest / ".config").symlink_to(dest / "real")
            with self.assertRaises(ValueError): setup.reject_symlinks(dest, ".config/file")
            with self.assertRaises(ValueError): setup.destination_path(dest / ".config/another")

    def test_destination_changed_after_plan(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest = Path(tmp) / "home"
            dest.mkdir()
            path = dest / "file"
            path.write_text("old")
            pending = setup.changes({"file": {"content": b"new", "mode": 0o644}}, dest)
            path.write_text("user changed this")
            with self.assertRaises(ValueError): setup.apply_files(pending, dest, Path(tmp) / "backup")
            self.assertEqual(path.read_text(), "user changed this")

    def test_recovery_preserves_post_apply_edits(self):
        with tempfile.TemporaryDirectory() as tmp:
            dest, backup = Path(tmp) / "home", Path(tmp) / "backup"
            dest.mkdir()
            pending = setup.changes({"file": {"content": b"ours", "mode": 0o644}}, dest)
            setup.apply_files(pending, dest, backup)
            (dest / "file").write_text("later user work")
            with self.assertRaises(ValueError): recover.recovery_plan(backup / "manifest.json", dest)
            self.assertEqual((dest / "file").read_text(), "later user work")

    def test_recovery_destination_must_match(self):
        with tempfile.TemporaryDirectory() as tmp:
            manifest = Path(tmp) / "manifest.json"
            manifest.write_text(json.dumps({"version": 1, "destination": "/different", "files": []}))
            with self.assertRaises(ValueError): recover.recovery_plan(manifest, tmp)


class SafetyTests(unittest.TestCase):
    def test_missing_css_resource_is_reported(self):
        files = {".config/waybar/style.css": {"content": b'@import "themes/missing.css";'}}
        with self.assertRaises(ValueError): validate.validate_resources(files, "/test/home")

    def test_fish_values_are_decoded_not_executed(self):
        self.assertEqual(capture.decode_fish_value(r"red\x1e\u27a4"), ["red", "➤"])
        self.assertEqual(capture.decode_fish_value(r"\x1d"), [])
        with self.assertRaises(ValueError): capture.decode_fish_value(r"\q")

    def test_source_tree(self):
        self.assertEqual(safety.check_tree(ROOT), [])

    def test_synthetic_secrets_without_values_in_findings(self):
        samples = ["pass" + "word=example-literal", "https://" + "user:literal@example.invalid", "-----BEGIN " + "PRIVATE KEY-----", "ghp_" + "x" * 35]
        for text in samples:
            with self.subTest(kind=text[:3]):
                self.assertTrue(safety.findings(text))
                with self.assertRaises(ValueError) as result: safety.check_text(text, "example")
                self.assertNotIn(text, str(result.exception))

    def test_environment_reference_is_not_a_literal(self):
        self.assertEqual(safety.findings('api_key="{env:LOCAL_VALUE}"'), [])

    def test_denied_filename(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "auth.json").write_text("{}")
            self.assertTrue(safety.check_tree(tmp))

    def test_unapproved_binary(self):
        with tempfile.TemporaryDirectory() as tmp:
            (Path(tmp) / "program").write_bytes(b"\xff\xfe\x00")
            self.assertTrue(safety.check_tree(tmp))

    @unittest.skipUnless(shutil.which("git"), "Git unavailable in isolated environment")
    def test_staged_blob_is_checked_even_when_working_file_is_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            env = {**os.environ, "GIT_CONFIG_GLOBAL": "/dev/null", "GIT_CONFIG_NOSYSTEM": "1"}
            def git(*args): subprocess.run(["git", *args], cwd=root, env=env, check=True, capture_output=True)
            git("init", "-q")
            synthetic = "ghp_" + "x" * 35
            (root / "example.txt").write_text(synthetic)
            git("add", "example.txt")
            (root / "example.txt").write_text("safe working tree\n")
            with mock.patch.object(validate, "ROOT", root), self.assertRaises(ValueError) as result:
                validate.scan_secrets()
            self.assertNotIn(synthetic, str(result.exception))


@unittest.skipUnless(shutil.which("chezmoi"), "Chezmoi unavailable in this isolated environment")
class TemplateTests(unittest.TestCase):
    def render_profile(self, tmp, preset, hw):
        dest = Path(tmp) / "home"
        data = plan(["--preset", preset, "--destination", str(dest)], hardware=hw)["portable"]
        files = setup.render(Path(tmp) / "work", dest, data)
        validate.validate_resources(files, dest)
        return files

    def test_minimal_laptop(self):
        with tempfile.TemporaryDirectory() as tmp:
            files = self.render_profile(tmp, "minimal", HW)
            self.assertIn(".config/hypr/hyprland.conf", files)
            self.assertNotIn(".config/opencode/opencode.jsonc", files)
            hypr = files[".config/hypr/hyprland.conf"]["content"].decode()
            self.assertNotIn("wayland-1", hypr)
            self.assertNotIn("obsidian-special.sh", hypr)
            bar = json.loads(files[".config/waybar/config.jsonc"]["content"])
            self.assertEqual(bar["battery"]["bat"], "BAT9")
            self.assertEqual(bar["backlight"]["device"], "test_backlight")

    def test_full_desktop_twice(self):
        hw = {**HW, "profile": "desktop", "battery": "", "backlight": ""}
        with tempfile.TemporaryDirectory() as tmp:
            files = self.render_profile(tmp, "full", hw)
            dest = Path(tmp) / "home"
            self.assertGreater(len(files), 500)
            self.assertTrue(files[".config/opencode/gsd-core/bin/gsd_run"]["mode"] & 0o111)
            self.assertIn(".config/opencode/gsd-core/references/verification-patterns.md", files)
            self.assertNotIn("1800", files[".config/hypr/hypridle.conf"]["content"].decode())
            for name, item in files.items():
                if not name.endswith((".jpg", ".png")):
                    self.assertNotIn(str(Path.home()) + "/", item["content"].decode(), name)
                    self.assertNotIn("__HOME__", item["content"].decode(), name)
            setup.apply_files(setup.changes(files, dest), dest, Path(tmp) / "backup")
            rerendered = self.render_profile(tmp, "full", hw)
            self.assertEqual(setup.changes(rerendered, dest), [])


if __name__ == "__main__":
    unittest.main()
