"""Проверки парсера и прототипа."""
import contextlib
import io
import unittest
from src.shell import Shell


class ShellTests(unittest.TestCase):
    """Проверяет кавычки, ошибки и завершение."""

    def test_quotes(self):
        """Пробелы и пустые аргументы сохраняются в кавычках."""
        shell = Shell()
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertTrue(shell.execute("ls \"a b\" 'c d' \"\""))
        self.assertIn("['a b', 'c d', '']", output.getvalue())

    def test_errors(self):
        """Ошибочный ввод не завершает сеанс."""
        shell = Shell()
        for line in ['unknown', 'ls "oops', 'exit extra']:
            with self.subTest(line=line):
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertFalse(shell.execute(line))
                self.assertTrue(shell.running)

    def test_exit(self):
        """Команда exit останавливает цикл."""
        shell = Shell()
        self.assertTrue(shell.execute(''))
        self.assertTrue(shell.execute('exit'))
        self.assertFalse(shell.running)
