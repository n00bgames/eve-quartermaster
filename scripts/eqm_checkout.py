"""Check Git checkout permissions before updating; explicitly repair source ownership on POSIX."""
from __future__ import annotations

import argparse
import os
import stat
import subprocess
import sys
from pathlib import Path


class CheckoutError(Exception):
    pass


def checkout_paths(root: Path) -> list[Path]:
    """Only tracked source, its parents and Git metadata; never runtime volumes."""
    root = root.resolve()
    metadata = root / ".git"
    if metadata.is_symlink() or not metadata.is_dir():
        raise CheckoutError("Use a regular Git checkout with its own .git directory for host updates.")
    result = subprocess.run(
        ["git", "-c", f"safe.directory={root}", "ls-files", "--cached", "-z"],
        cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True, timeout=30,
    )
    paths = {root, metadata}
    for name in result.stdout.split(b"\0"):
        if not name:
            continue
        relative = Path(os.fsdecode(name))
        if relative.is_absolute() or ".." in relative.parts:
            raise CheckoutError("Git returned a source path outside this checkout.")
        path = root / relative
        # Do not resolve a tracked link or follow linked parent directories.
        for parent in path.parents:
            if parent == root:
                break
            if parent.is_symlink():
                raise CheckoutError(f"Linked source directory needs manual review: {parent.relative_to(root)}")
            paths.add(parent)
        paths.add(path)
    for directory, dirs, files in os.walk(metadata, followlinks=False):
        for name in [*dirs, *files]:
            path = Path(directory) / name
            if path.is_symlink():
                raise CheckoutError("Linked Git metadata needs manual review before updating.")
            paths.add(path)
    return sorted(paths, key=lambda p: (len(p.parts), str(p)))


def permission_issues(root: Path) -> list[str]:
    root = root.resolve()
    issues = []
    owner = os.geteuid() if os.name == "posix" else None
    for path in checkout_paths(root):
        try:
            info = path.lstat()
        except FileNotFoundError:
            # Missing source is a local Git change, handled by the clean-tree check.
            continue
        label = str(path.relative_to(root))
        if owner is not None and info.st_uid != owner:
            issues.append(f"{label} (owned by uid {info.st_uid})")
            continue
        if stat.S_ISLNK(info.st_mode):
            continue
        if stat.S_ISDIR(info.st_mode):
            allowed = os.access(path, os.R_OK | os.W_OK | os.X_OK)
        elif stat.S_ISREG(info.st_mode):
            # Git replaces tracked files via their parent directory, but opens
            # refs/index/config in place. Object/pack files may be read-only.
            metadata_file = path.is_relative_to(root / ".git")
            needs_write = metadata_file and not path.is_relative_to(root / ".git/objects")
            allowed = os.access(path, os.R_OK | (os.W_OK if needs_write else 0))
        else:
            allowed = False
        if not allowed:
            issues.append(f"{label} (insufficient access)")
    return issues


def assert_checkout_writable(root: Path) -> None:
    if os.name == "posix" and os.geteuid() == 0:
        raise CheckoutError("Run EQM updates as the checkout owner, without sudo or root.")
    issues = permission_issues(root)
    if issues:
        examples = "; ".join(issues[:3])
        raise CheckoutError(
            f"Checkout permissions block this host account: {examples} ({len(issues)} affected paths). "
            "No update was started. See docs/application-updates.md#checkout-permissions for the scoped ownership repair."
        )


def repair_owner(root: Path, account: str) -> int:
    if os.name != "posix" or os.geteuid() != 0:
        raise CheckoutError("Ownership repair requires sudo on the POSIX Docker host.")
    import pwd

    user = pwd.getpwnam(account)
    if user.pw_uid == 0:
        raise CheckoutError("Choose the unprivileged account that normally owns and runs EQM.")
    root = root.resolve()
    # Validate the entire bounded set before changing anything. Symlinks used
    # as tracked files are chowned themselves, never their targets.
    paths = checkout_paths(root)
    changed = 0
    for path in paths:
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if not (stat.S_ISREG(info.st_mode) or stat.S_ISDIR(info.st_mode) or stat.S_ISLNK(info.st_mode)):
            raise CheckoutError(f"Unexpected file type needs manual review: {path.relative_to(root)}")
        if stat.S_ISREG(info.st_mode) and info.st_nlink > 1:
            raise CheckoutError(f"Hard-linked file needs manual review before ownership repair: {path.relative_to(root)}")
    for path in paths:
        try:
            info = path.lstat()
        except FileNotFoundError:
            continue
        if info.st_uid != user.pw_uid or info.st_gid != user.pw_gid:
            os.chown(path, user.pw_uid, user.pw_gid, follow_symlinks=False)
            changed += 1
        if not stat.S_ISLNK(info.st_mode):
            wanted = stat.S_IMODE(info.st_mode) | (0o700 if stat.S_ISDIR(info.st_mode) else 0o600)
            if wanted != stat.S_IMODE(info.st_mode):
                path.chmod(wanted)
    return changed


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument("--repair-owner", metavar="ACCOUNT", help="Explicitly repair tracked source and Git metadata ownership using sudo")
    args = parser.parse_args()
    try:
        if args.repair_owner:
            count = repair_owner(args.root, args.repair_owner)
            print(f"Repaired ownership on {count} checkout paths. Runtime volumes, .env and untracked files were excluded.")
        else:
            assert_checkout_writable(args.root)
            print("Checkout permissions OK.")
    except (CheckoutError, OSError, KeyError, subprocess.SubprocessError) as exc:
        sys.exit(f"Update stopped: {exc}")


if __name__ == "__main__":
    main()
