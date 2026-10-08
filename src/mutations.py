"""Дополнительные команды: изменения только объектов памяти."""
import re
from src.commands import arguments

OWNER_FIELDS = 2
MIN_CHOWN_ARGS = 2
SINGLE_FIELD = 1

OWNER_PATTERN = r"[A-Za-z_][A-Za-z0-9_.-]*|[0-9]+"


class Mutations:
    """Меняет время и владельцев узлов виртуальной системы."""

    def __init__(self, commands):
        """Использует общие правила разрешения виртуальных путей."""
        self.commands = commands
        self.vfs = commands.shell.vfs

    def touch(self, name, args):
        """touch [-c] [--] путь ...: создаёт файл или обновляет mtime."""
        flags, paths = arguments(args, "c")
        if not paths:
            raise ValueError("touch: укажите хотя бы один путь")
        for value in paths:
            self.vfs.touch(self.commands.path(value), "c" in flags)

    def chown(self, name, args):
        """chown [-R] владелец[:группа] путь ...: меняет метаданные."""
        flags, parts = arguments(args, "R")
        if len(parts) < MIN_CHOWN_ARGS:
            raise ValueError("chown: укажите владельца и путь")
        owner, group = self.owner_spec(parts[0])
        for value in parts[1:]:
            root = self.commands.path(value)
            entries = self.vfs.subtree(root) if "R" in flags else [root]
            for path in entries:
                node = self.vfs.get(path)
                if owner:
                    node.owner = owner
                if group:
                    node.group = group

    def owner_spec(self, value):
        """Разбирает имя/UID, owner:group либо :group без системных прав."""
        parts = value.split(":")
        if len(parts) > OWNER_FIELDS or not any(parts):
            raise ValueError("chown: неверный формат владельца")
        for part in parts:
            if part and not re.fullmatch(OWNER_PATTERN, part):
                raise ValueError("chown: неверное имя или идентификатор")
        if len(parts) > SINGLE_FIELD and not parts[1]:
            raise ValueError("chown: после ':' требуется группа")
        return parts[0], parts[1] if len(parts) > SINGLE_FIELD else None
