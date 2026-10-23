"""Снимок физического каталога; изменения существуют только в памяти."""
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
import getpass
import os
import stat
import time


@dataclass
class Node:
    """Файл или каталог, его байты, владелец, группа и время изменения."""
    is_dir: bool
    data: bytes = b""
    owner: str = ""
    group: str = ""
    mtime: float = 0.0


def normalized(path, cwd="/"):
    """Нормализует виртуальный путь и ограничивает .. корнем VFS."""
    if not path:
        raise ValueError("пустой путь")
    parts = [] if path.startswith("/") else cwd.strip("/").split("/")
    for item in path.split("/"):
        if item == "..":
            parts = parts[:-1]
        elif item not in ("", "."):
            parts.append(item)
    return "/" + "/".join(part for part in parts if part)


class VFS:
    """Хранит все данные VFS в словаре абсолютных POSIX-путей."""

    def __init__(self, source):
        """Считывает каталог; ссылки и специальные файлы запрещены."""
        root = Path(source)
        if root.is_symlink() or not root.is_dir():
            raise ValueError(f"VFS: нужен существующий каталог: {source}")
        self.nodes = {}
        self._load(root, "/")

    def _load(self, physical, virtual):
        """Рекурсивно загружает обычные файлы и каталоги без записи."""
        info = physical.lstat()
        directory = stat.S_ISDIR(info.st_mode)
        if not directory and not stat.S_ISREG(info.st_mode):
            raise ValueError(f"VFS: неподдерживаемый объект: {physical}")
        data = b"" if directory else physical.read_bytes()
        self.nodes[virtual] = Node(directory, data, str(info.st_uid),
                                   str(info.st_gid), info.st_mtime)
        if directory:
            for child in sorted(physical.iterdir()):
                self._load(child, normalized(child.name, virtual))

    def resolve(self, path, cwd="/"):
        """Проверяет компоненты до ..; последний файл может отсутствовать."""
        if not path:
            raise ValueError("пустой путь")
        current = "/" if path.startswith("/") else cwd
        parts = path.split("/")
        for index, part in enumerate(parts):
            if not self.get(current).is_dir:
                raise ValueError(f"не каталог: {current}")
            current = normalized(part or ".", current)
            if index < len(parts) - 1:
                self.get(current)
        return current

    def get(self, path):
        """Получает объект с проверкой промежуточных каталогов."""
        for parent in PurePosixPath(path).parents:
            if str(parent) in self.nodes:
                if not self.nodes[str(parent)].is_dir:
                    raise ValueError(f"не каталог: {parent}")
        if path not in self.nodes:
            raise ValueError(f"путь не найден: {path}")
        return self.nodes[path]

    def children(self, path):
        """Возвращает отсортированные пути непосредственных потомков."""
        if not self.get(path).is_dir:
            raise ValueError(f"не каталог: {path}")
        return sorted(key for key in self.nodes if key != path
                      and str(PurePosixPath(key).parent) == path)

    def subtree(self, path):
        """Возвращает объект и всех его потомков."""
        self.get(path)
        prefix = path.rstrip("/") + "/"
        return sorted(key for key in self.nodes
                      if key == path or key.startswith(prefix))

    def touch(self, path, no_create=False):
        """Создаёт пустой файл либо обновляет mtime существующего узла."""
        if path not in self.nodes:
            if no_create:
                return
            parent = str(PurePosixPath(path).parent)
            if not self.get(parent).is_dir:
                raise ValueError(f"не каталог: {parent}")
            self.nodes[path] = Node(False, owner=getpass.getuser(),
                                    group=str(os.getgid())
                                    if hasattr(os, "getgid") else "0")
        self.get(path).mtime = time.time()
