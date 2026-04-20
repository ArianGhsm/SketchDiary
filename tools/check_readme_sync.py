import ast
import subprocess
import sys
from pathlib import Path


CODE_EXTENSIONS = {
    ".py",
    ".sql",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
}

CODE_FILES = {
    "main.py",
    "db.py",
    "grade_analytics.py",
    "import_students.py",
    "config.py",
    "app_callbacks.py",
    "assistant_profile.py",
    "text_utils.py",
}

DOC_FILES = {
    "README.md",
    "ARCHITECTURE_FA.md",
    "INLINE_UX_POLICY_FA.md",
    "CONTRIBUTING_FA.md",
    "AGENTS.md",
}

DEP_MODULE_TO_REQUIREMENT = {
    "telegram": "python-telegram-bot",
}


def run_git(args: list[str]) -> str:
    result = subprocess.run(
        ["git", *args],
        check=False,
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        return ""
    return result.stdout


def changed_files(staged: bool) -> list[str]:
    diff_args = ["diff", "--name-only"]
    if staged:
        diff_args.append("--cached")
    output = run_git(diff_args).strip()
    if not output:
        return []
    return [line.strip().replace("\\", "/") for line in output.splitlines() if line.strip()]


def is_code_file(path_str: str) -> bool:
    path = Path(path_str)
    if path.name in CODE_FILES:
        return True
    return path.suffix.lower() in CODE_EXTENSIONS


def parse_requirements(requirements_path: Path) -> set[str]:
    packages: set[str] = set()
    if not requirements_path.exists():
        return packages

    for raw_line in requirements_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        base = line.split(";")[0].strip()
        for sep in ("==", ">=", "<=", "~=", "!=", ">", "<"):
            if sep in base:
                base = base.split(sep, 1)[0].strip()
                break
        normalized = base.lower().replace("_", "-")
        if normalized:
            packages.add(normalized)
    return packages


def parse_imported_modules(py_file: Path) -> set[str]:
    modules: set[str] = set()
    try:
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
    except (SyntaxError, UnicodeDecodeError, OSError):
        return modules

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".", 1)[0]
                if root:
                    modules.add(root)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                root = node.module.split(".", 1)[0]
                if root:
                    modules.add(root)
    return modules


def local_module_names(repo_root: Path) -> set[str]:
    names: set[str] = set()
    for py_file in repo_root.rglob("*.py"):
        if py_file.name == "__init__.py":
            names.add(py_file.parent.name)
            continue
        names.add(py_file.stem)
    return names


def dependency_sync_check(repo_root: Path, changed: list[str]) -> tuple[bool, str]:
    py_changed = [
        repo_root / path
        for path in changed
        if path.endswith(".py") and (repo_root / path).exists()
    ]
    if not py_changed:
        return True, ""

    stdlib = set(getattr(sys, "stdlib_module_names", set()))
    locals_set = local_module_names(repo_root)
    requirements = parse_requirements(repo_root / "requirements.txt")

    imported = set()
    for py_file in py_changed:
        imported |= parse_imported_modules(py_file)

    third_party = {
        module
        for module in imported
        if module not in stdlib and module not in locals_set
    }

    missing_requirements = []
    for module in sorted(third_party):
        mapped_requirement = DEP_MODULE_TO_REQUIREMENT.get(module, module).lower().replace("_", "-")
        if mapped_requirement not in requirements:
            missing_requirements.append((module, mapped_requirement))

    if not missing_requirements:
        return True, ""

    lines = [
        "ERROR: Python imports changed but requirements.txt is not in sync.",
        "Missing mappings:",
    ]
    for module, requirement in missing_requirements:
        lines.append(f"- import '{module}' requires requirement '{requirement}'")
    lines.append("Please update requirements.txt in the same commit.")
    return False, "\n".join(lines)


def main() -> int:
    staged = "--staged" in sys.argv
    files = changed_files(staged=staged)
    if not files:
        return 0

    changed_set = set(files)
    code_changed = any(is_code_file(file_path) for file_path in files)
    readme_changed = "README.md" in changed_set
    requirements_changed = "requirements.txt" in changed_set

    if code_changed and not readme_changed:
        print("ERROR: Code changes detected but README.md is not updated.")
        print("Please update README.md in the same change.")
        print("")
        print("Changed files:")
        for file_path in files:
            print(f"- {file_path}")
        return 1

    docs_changed = any(file_path in DOC_FILES for file_path in files)
    if docs_changed and not readme_changed and not code_changed:
        print("Info: documentation changed without README.md; allowed.")

    ok, dep_message = dependency_sync_check(Path.cwd(), files)
    if not ok:
        print(dep_message)
        return 1

    if code_changed and not requirements_changed:
        print(
            "Info: requirements.txt unchanged. "
            "If no dependency/import changed, this is fine."
        )

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
