"""Точка входа в эмулятор."""
from src.shell import Shell


def main():
    """Запускает интерактивный прототип."""
    Shell().repl()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
