"""Основные команды над снимком VFS."""
from datetime import datetime
from pathlib import PurePosixPath
from src.vfs import normalized

DEFAULT_TAIL_LINES = 10
MIN_LINE_COUNT = 0
SINGLE_PATH = 1
OPTION_PAIR_SIZE = 2


def arguments(args, supported):
    """Отделяет короткие флаги от путей; -- завершает разбор флагов."""
    flags, paths = set(), []
    options = True
    for arg in args:
        if options and arg == "--":
            options = False
        elif options and arg.startswith("-") and arg != "-":
            unknown = set(arg[1:]) - set(supported)
            if unknown:
                raise ValueError(f"неподдерживаемая опция: {arg}")
            flags.update(arg[1:])
        else:
            paths.append(arg)
    return flags, paths


class Commands:
    """Выполняет ls, cd, du и tail в пределах VFS."""

    def __init__(self, shell):
        """Сохраняет сеанс оболочки."""
        self.shell = shell

    def path(self, value):
        """Разрешает путь относительно текущего каталога VFS."""
        return self.shell.vfs.resolve(value, self.shell.cwd)

    def listing(self, name, args):
        """ls [-al] [--] [путь ...]: содержимое и метаданные."""
        flags, paths = arguments(args, "al")
        for value in paths or ["."]:
            path = self.path(value)
            node = self.shell.vfs.get(path)
            entries = self.shell.vfs.children(path) if node.is_dir else [path]
            if len(paths) > SINGLE_PATH:
                print(f"{value}:")
            for entry in entries:
                label = PurePosixPath(entry).name or "/"
                if node.is_dir and label.startswith(".") and "a" not in flags:
                    continue
                self.print_entry(entry, label, "l" in flags)

    def print_entry(self, path, label, detailed):
        """Печатает имя либо тип, владельца, группу, размер и mtime."""
        node = self.shell.vfs.get(path)
        if not detailed:
            print(label)
            return
        kind = "d" if node.is_dir else "-"
        stamp = datetime.fromtimestamp(node.mtime).isoformat(timespec="seconds")
        print(f"{kind} {node.owner}:{node.group} "
              f"{len(node.data)} {stamp} {label}")

    def cd(self, name, args):
        """cd [--] [каталог]: меняет только виртуальный каталог."""
        _, paths = arguments(args, "")
        if len(paths) > SINGLE_PATH:
            raise ValueError("cd: ожидается не более одного пути")
        path = normalized(paths[0] if paths else "/", self.shell.cwd)
        if not self.shell.vfs.get(path).is_dir:
            raise ValueError(f"cd: не каталог: {path}")
        self.shell.cwd = path

    def du(self, name, args):
        """du [-sa] [--] [путь ...]: логические размеры в байтах."""
        flags, paths = arguments(args, "sa")
        if {"s", "a"} <= flags:
            raise ValueError("du: -s и -a несовместимы")
        for value in paths or ["."]:
            root = self.path(value)
            entries = self.shell.vfs.subtree(root)
            sizes = self.sizes(entries)
            for path in sorted(entries, key=lambda item: (-item.count('/'),
                                                          item)):
                node = self.shell.vfs.get(path)
                show = path == root or "a" in flags or node.is_dir
                if show and ("s" not in flags or path == root):
                    print(f"{sizes[path]}\t{path}")

    def sizes(self, entries):
        """Суммирует длины файлов, не учитывая дисковые блоки каталогов."""
        totals = {path: len(self.shell.vfs.get(path).data) for path in entries}
        for path in sorted(entries, key=len, reverse=True):
            parent = str(PurePosixPath(path).parent)
            if parent in totals and parent != path:
                totals[parent] += totals[path]
        return totals

    def tail(self, name, args):
        """tail [-n N] [--] файл ...: последние N строк UTF-8."""
        count, paths = self.tail_args(args)
        for value in paths:
            path = self.path(value)
            node = self.shell.vfs.get(path)
            if node.is_dir:
                raise ValueError(f"tail: это каталог: {path}")
            text = node.data.decode("utf-8").replace("\r\n", "\n")
            if len(paths) > SINGLE_PATH:
                print(f"==> {value} <==")
            lines = text.splitlines(keepends=True)
            print("".join(lines[-count:]) if count else "", end="")

    def tail_args(self, args):
        """Проверяет число строк и обязательные имена файлов."""
        count = DEFAULT_TAIL_LINES
        if args[:1] == ["-n"]:
            if len(args) < OPTION_PAIR_SIZE:
                raise ValueError("tail: после -n требуется число")
            try:
                count = int(args[1])
            except ValueError as error:
                raise ValueError("tail: N должно быть целым") from error
            args = args[2:]
        if count < MIN_LINE_COUNT:
            raise ValueError("tail: N не может быть отрицательным")
        _, paths = arguments(args, "")
        if not paths:
            raise ValueError("tail: укажите файл")
        return count, paths


def install(shell):
    """Подключает команды к сеансу."""
    from src.mutations import Mutations

    commands = Commands(shell)
    shell.commands = {"ls": commands.listing, "cd": commands.cd,
                      "du": commands.du, "tail": commands.tail}

    mutations = Mutations(commands)
    shell.commands.update({"touch": mutations.touch,
                           "chown": mutations.chown})
