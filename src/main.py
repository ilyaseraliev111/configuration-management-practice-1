"""Параметры запуска, стартовый сценарий и интерактивный режим."""
import argparse
from pathlib import Path
from src.shell import Shell


def parse_args(argv=None):
    """Разбирает пути VFS и сценария, а также режим без REPL."""
    parser = argparse.ArgumentParser(description="Эмулятор, вариант 28")
    parser.add_argument("--vfs", default="examples/vfs/demo")
    parser.add_argument("--script", help="Стартовый сценарий UTF-8")
    parser.add_argument("--batch", action="store_true",
                        help="Завершиться после сценария без REPL")
    return parser.parse_args(argv)


def run_script(shell, path):
    """Показывает диалог; первая ошибка останавливает сценарий."""
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    for number, line in enumerate(lines, start=1):
        if not shell.running:
            break
        print(shell.prompt + line)
        if not shell.execute(line):
            print(f"Ошибка сценария {path}, строка {number}")
            return False
    return True


def main(argv=None):
    """Запускает сценарий и REPL; при ошибке возвращает код 1."""
    args = parse_args(argv)
    print(f"VFS: {args.vfs}")
    print(f"Сценарий: {args.script or '(не задан)'}")
    print(f"Пакетный режим: {args.batch}")
    shell = Shell()
    try:
        if args.script and not run_script(shell, args.script):
            return 1
        if not args.batch:
            shell.repl()
    except (OSError, ValueError) as error:
        print(f"Ошибка запуска: {error}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
