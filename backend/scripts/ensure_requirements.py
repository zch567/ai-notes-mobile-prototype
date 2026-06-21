from __future__ import annotations

import importlib.metadata as metadata
import os
import platform
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path


REQ_PATTERN = re.compile(r"^\s*([A-Za-z0-9_.-]+)\s*(.*)$")


@dataclass(frozen=True)
class Requirement:
    name: str
    spec: str
    raw: str


def _read_requirements(path: Path) -> list[Requirement]:
    requirements: list[Requirement] = []
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if not line:
            continue
        requirement_text, separator, marker = line.partition(";")
        if separator and not _marker_applies(marker.strip()):
            continue
        match = REQ_PATTERN.match(requirement_text.strip())
        if match:
            requirements.append(Requirement(match.group(1), match.group(2).strip(), raw.strip()))
    return requirements


def _marker_applies(marker: str) -> bool:
    match = re.fullmatch(r"""platform_system\s*(==|!=)\s*["']([^"']+)["']""", marker)
    if not match:
        return True
    operator, expected = match.groups()
    matches = platform.system().lower() == expected.lower()
    return matches if operator == "==" else not matches


def _version_key(version: str) -> tuple[tuple[int, int | str], ...]:
    parts: list[tuple[int, int | str]] = []
    for part in re.split(r"[.\-+_]", version):
        if not part:
            continue
        match = re.match(r"^(\d+)(.*)$", part)
        if match:
            parts.append((0, int(match.group(1))))
            suffix = match.group(2)
            if suffix:
                parts.append((1, suffix))
        else:
            parts.append((1, part))
    return tuple(parts)


def _compare_versions(left: str, right: str) -> int:
    left_key = _version_key(left)
    right_key = _version_key(right)
    max_len = max(len(left_key), len(right_key))
    left_padded = left_key + ((0, 0),) * (max_len - len(left_key))
    right_padded = right_key + ((0, 0),) * (max_len - len(right_key))
    return (left_padded > right_padded) - (left_padded < right_padded)


def _satisfies(version: str, spec: str) -> bool:
    if not spec:
        return True
    for clause in [item.strip() for item in spec.split(",") if item.strip()]:
        operator = next((op for op in (">=", "<=", "==", ">", "<") if clause.startswith(op)), "")
        if not operator:
            continue
        expected = clause[len(operator) :].strip()
        comparison = _compare_versions(version, expected)
        if operator == ">=" and comparison < 0:
            return False
        if operator == "<=" and comparison > 0:
            return False
        if operator == "==" and comparison != 0:
            return False
        if operator == ">" and comparison <= 0:
            return False
        if operator == "<" and comparison >= 0:
            return False
    return True


def _find_install_issues(requirements: list[Requirement]) -> list[str]:
    issues: list[str] = []
    for requirement in requirements:
        try:
            installed_version = metadata.version(requirement.name)
        except metadata.PackageNotFoundError:
            issues.append(f"{requirement.name}: not installed")
            continue
        if not _satisfies(installed_version, requirement.spec):
            issues.append(f"{requirement.name}: installed {installed_version}, required {requirement.spec}")
    return issues


def ensure_backend_requirements(backend_root: Path | None = None) -> None:
    if os.getenv("BACKEND_SKIP_DEP_INSTALL") == "1":
        print("[backend] Dependency auto-install skipped by BACKEND_SKIP_DEP_INSTALL=1.")
        return

    root = backend_root or Path(__file__).resolve().parents[1]
    requirements_path = root / "requirements.txt"
    if not requirements_path.exists():
        raise FileNotFoundError(f"requirements.txt not found: {requirements_path}")

    requirements = _read_requirements(requirements_path)
    issues = _find_install_issues(requirements)
    if not issues:
        print("[backend] Python dependencies are ready.")
        return

    print("[backend] Missing or incompatible Python dependencies:")
    for issue in issues:
        print(f"  - {issue}")

    command = [sys.executable, "-m", "pip", "install", "-r", str(requirements_path)]
    print("[backend] Installing dependencies with:")
    print(f"  {' '.join(command)}")

    result = subprocess.run(command, cwd=str(root), check=False)
    if result.returncode != 0:
        raise SystemExit(
            "\n[backend] Dependency installation failed. "
            f"Please run manually: {' '.join(command)}"
        )

    remaining = _find_install_issues(requirements)
    if remaining:
        details = "\n".join(f"  - {issue}" for issue in remaining)
        raise SystemExit(f"\n[backend] Dependencies are still not ready:\n{details}")

    print("[backend] Dependencies installed successfully.")


if __name__ == "__main__":
    ensure_backend_requirements()
