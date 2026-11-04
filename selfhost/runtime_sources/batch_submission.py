"""Bounded extraction of one complete, six-task prediction submission."""
from __future__ import annotations

import os
from pathlib import Path
import stat
import zipfile

BUNDLE_FILES = {
    "hstu": "hstu/submission.npz",
    "tiger": "tiger/submission.npz",
    "intsr": "intsr/submission.npz",
    "wukong": "wukong/submission.csv.gz",
    "rankmixer": "rankmixer/submission.npz",
    "onetrans": "onetrans/submission.csv",
}
MAX_BUNDLE_BYTES = 512 * 1024**2
MAX_MEMBER_BYTES = 160 * 1024**2
MAX_EXPANDED_BYTES = 6 * MAX_MEMBER_BYTES
MAX_DIRECTORY_BYTES = 2 * 1024**2
ERROR = "Invalid ZIP: provide exactly the six task prediction files in their task folders."


def _require(condition):
    if not condition:
        raise ValueError(ERROR)


def _identity(metadata):
    return metadata.st_dev, metadata.st_ino


def _safe_chain(directory):
    for path in (directory, *directory.parents):
        _require(not path.is_symlink() and (not path.exists() or path.is_dir()))


def _check_zip_metadata(path):
    # The pinned Python 3.12 helper reads only the bounded EOCD/ZIP64 records.
    # Inspect these before ZipFile allocates one object per central-directory entry.
    with path.open("rb") as stream:
        end = zipfile._EndRecData(stream)
    _require(end is not None and end[zipfile._ECD_DISK_NUMBER] == 0
             and end[zipfile._ECD_DISK_START] == 0
             and end[zipfile._ECD_ENTRIES_THIS_DISK] == end[zipfile._ECD_ENTRIES_TOTAL]
             and 6 <= end[zipfile._ECD_ENTRIES_TOTAL] <= 12
             and 0 <= end[zipfile._ECD_SIZE] <= MAX_DIRECTORY_BYTES)


def _check_archive(archive):
    infos = archive.infolist()
    names = [info.filename for info in infos]
    files = set(BUNDLE_FILES.values())
    directories = {task + "/" for task in BUNDLE_FILES}
    _require(6 <= len(infos) <= 12 and len(names) == len(set(names))
             and set(names) <= files | directories and files <= set(names))
    result = {}
    for info in infos:
        name = info.filename
        _require(not name.startswith("/") and "\\" not in name
                 and all(part not in ("", ".", "..") for part in name.rstrip("/").split("/")))
        mode = stat.S_IFMT(info.external_attr >> 16)
        _require(not info.flag_bits & 1 and info.compress_type in (zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED))
        if name in directories:
            _require(info.is_dir() and info.file_size == 0 and mode in (0, stat.S_IFDIR))
        else:
            _require(not info.is_dir() and mode in (0, stat.S_IFREG)
                     and 0 <= info.file_size <= MAX_MEMBER_BYTES)
            result[name] = info
    _require(sum(info.file_size for info in result.values()) <= MAX_EXPANDED_BYTES)
    return result


def _copy_member(source, target, expected_size):
    written = 0
    while chunk := source.read(1024 * 1024):
        written += len(chunk)
        _require(written <= expected_size and written <= MAX_MEMBER_BYTES)
        target.write(chunk)
    _require(written == expected_size)
    return written


def unpack_submission_bundle(path: Path, destination: Path) -> dict[str, Path]:
    """Extract only canonical files; callers separately validate each prediction.

    The destination must be new or empty and its parent must already exist.
    File writes are anchored to directory descriptors and never follow ZIP paths.
    """
    root_fd = None
    task_fds = {}
    created_files = []
    created_directories = []
    root_created = False
    original_mode = None
    succeeded = False
    try:
        path, root = Path(path), Path(destination).absolute()
        _require(not path.is_symlink() and path.is_file() and 0 < path.stat().st_size <= MAX_BUNDLE_BYTES)
        _safe_chain(root)
        _require(root.parent.is_dir())
        if root.exists():
            _require(not any(root.iterdir()))
        _check_zip_metadata(path)
        with zipfile.ZipFile(path) as archive:
            members = _check_archive(archive)
            if not root.exists():
                root.mkdir(mode=0o700)
                root_created = True
            original = root.lstat()
            root_fd = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
            _require(_identity(os.fstat(root_fd)) == _identity(original) and not os.listdir(root_fd))
            original_mode = stat.S_IMODE(original.st_mode)
            os.fchmod(root_fd, 0o700)
            total = 0
            for task, relative in BUNDLE_FILES.items():
                os.mkdir(task, mode=0o700, dir_fd=root_fd)
                created_directories.append(task)
                task_fd = os.open(task, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=root_fd)
                task_fds[task] = task_fd
                os.fchmod(task_fd, 0o700)
                filename = relative.split("/")[1]
                info = members[relative]
                with archive.open(info) as source:
                    descriptor = os.open(filename, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                                         0o600, dir_fd=task_fd)
                    created_files.append((task, filename, _identity(os.fstat(descriptor))))
                    with os.fdopen(descriptor, "wb") as target:
                        os.fchmod(target.fileno(), 0o600)
                        total += _copy_member(source, target, info.file_size)
                        _require(total <= MAX_EXPANDED_BYTES)
            _safe_chain(root)
            _require(_identity(root.lstat()) == _identity(os.fstat(root_fd)))
            for task, filename, identity in created_files:
                _require(_identity(os.stat(task, dir_fd=root_fd, follow_symlinks=False)) == _identity(os.fstat(task_fds[task]))
                         and _identity(os.stat(filename, dir_fd=task_fds[task], follow_symlinks=False)) == identity)
        succeeded = True
        return {task: root / relative for task, relative in BUNDLE_FILES.items()}
    except Exception:
        raise ValueError(ERROR) from None
    finally:
        if not succeeded and root_fd is not None:
            for task, filename, identity in reversed(created_files):
                try:
                    if _identity(os.stat(filename, dir_fd=task_fds[task], follow_symlinks=False)) == identity:
                        os.unlink(filename, dir_fd=task_fds[task])
                except OSError:
                    pass
            for task in reversed(created_directories):
                try:
                    os.rmdir(task, dir_fd=root_fd)
                except OSError:
                    pass
            if original_mode is not None:
                try:
                    os.fchmod(root_fd, original_mode)
                except OSError:
                    pass
            if root_created:
                try:
                    if _identity(root.lstat()) == _identity(os.fstat(root_fd)):
                        root.rmdir()
                except OSError:
                    pass
        for descriptor in task_fds.values():
            os.close(descriptor)
        if root_fd is not None:
            os.close(root_fd)
