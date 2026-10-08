"""Разбор ввода и цикл взаимодействия с пользователем."""

import getpass
import shlex
import socket


class Shell:
    """Обрабатывает команды без вызова оболочки реальной ОС."""

    def __init__(self):
        """Получает настоящее имя пользователя и имя компьютера."""
        self.user = getpass.getuser()
        self.host = socket.gethostname()
        self.cwd = "/"
        self.running = True
        self.commands = {"ls": self.stub, "cd": self.stub}
        self.vfs = None

    @property
    def prompt(self):
        """Возвращает приглашение с виртуальным текущим каталогом."""
        return f"{self.user}@{self.host}:{self.cwd}$ "

    def stub(self, name, args):
        """Печатает имя команды и разобранные аргументы прототипа."""
        print(f"{name}: {args!r}")

    def execute(self, line):
        """Исполняет строку; возвращает False при ошибке."""
        try:
            parts = shlex.split(line, comments=False, posix=True)
            if not parts:
                return True
            name, *args = parts
            if name == "exit":
                if args:
                    raise ValueError("exit: аргументы не поддерживаются")
                self.running = False
            elif name in self.commands:
                self.commands[name](name, args)
            else:
                raise ValueError(f"неизвестная команда: {name}")
            return True
        except (ValueError, OSError) as error:
            print(f"Ошибка: {error}")
            return False

    def repl(self):
        """Читает команды до exit или конца ввода; Ctrl+C отменяет ввод."""
        while self.running:
            try:
                line = input(self.prompt)
            except EOFError:
                print()
                break
            except KeyboardInterrupt:
                print()
                continue
            self.execute(line)
