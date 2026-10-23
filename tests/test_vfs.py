"""Проверки снимка, путей и всех команд варианта 28."""
import contextlib
import io
from pathlib import Path
import tempfile
import unittest
from src.commands import install
from src.main import main, run_script
from src.shell import Shell
from src.vfs import VFS, normalized


class VFSTests(unittest.TestCase):
    """Каждый тест работает с новым временным исходным каталогом."""

    def setUp(self):
        """Создаёт дерево с Unicode, пробелами и скрытым файлом."""
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / 'a/b/c').mkdir(parents=True)
        (self.root / 'a/b/c/data').write_bytes(b'1\n2\n3\n')
        (self.root / 'hello world').write_text('Привет\n', encoding='utf-8')
        (self.root / '.hidden').write_bytes(b'x')
        self.shell = Shell()
        self.shell.vfs = VFS(self.root)
        install(self.shell)

    def run_line(self, line, success=True):
        """Исполняет команду и возвращает перехваченный вывод."""
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertEqual(self.shell.execute(line), success, line)
        return output.getvalue()

    def test_paths(self):
        """.. ограничен корнем, пути разрешаются относительно cwd."""
        self.assertEqual(normalized('../../..', '/a'), '/')
        self.run_line('cd /a/b/c')
        self.run_line('cd .././..')
        self.assertEqual(self.shell.cwd, '/a')
        self.run_line('cd')
        self.assertEqual(self.shell.cwd, '/')

    def test_listing(self):
        """ls показывает скрытые файлы только с -a."""
        self.assertNotIn('.hidden', self.run_line('ls'))
        self.assertIn('.hidden', self.run_line('ls -a'))
        self.assertIn('hello world', self.run_line('ls -l "hello world"'))
        self.run_line('ls -z', False)
        self.run_line('cd "hello world"', False)

    def test_invalid_path_components(self):
        """.. не скрывает отсутствующий каталог или файл в пути."""
        before = {key: vars(node).copy()
                  for key, node in self.shell.vfs.nodes.items()}
        for prefix in ['"hello world"', 'missing']:
            for command in ['ls', 'du', 'tail', 'touch', 'chown user']:
                with self.subTest(prefix=prefix, command=command):
                    self.run_line(f'{command} {prefix}/../.hidden', False)
        after = {key: vars(node).copy()
                 for key, node in self.shell.vfs.nodes.items()}
        self.assertEqual(before, after)

    def test_trailing_slash(self):
        """Слеш после имени требует существующего каталога."""
        for command in ['ls', 'du', 'tail', 'touch', 'chown user']:
            with self.subTest(command=command):
                self.run_line(f'{command} "hello world/"', False)
        self.run_line('touch new/', False)
        self.assertNotIn('/new', self.shell.vfs.nodes)
        self.run_line('touch a/')
        self.assertIn('b', self.run_line('ls a/'))

    def test_valid_component_paths(self):
        """Корректные .., повторные слеши и относительные пути работают."""
        self.run_line('cd /a/b')
        result = self.run_line('tail ./c/../c//data')
        self.assertEqual(result, '1\n2\n3\n')
        self.run_line('touch c/../new')
        self.assertIn('/a/b/new', self.shell.vfs.nodes)
        self.assertEqual(self.run_line('tail /../../.hidden'), 'x')

    def test_logical_cd(self):
        """cd логически сокращает .., как обычная оболочка без ссылок."""
        self.run_line('cd "hello world/.."')
        self.assertEqual(self.shell.cwd, '/')
        self.run_line('cd missing/..')
        self.assertEqual(self.shell.cwd, '/')

    def test_tail(self):
        """Последние строки, ноль строк, UTF-8 и отсутствие файла."""
        self.assertEqual(self.run_line('tail -n 2 /a/b/c/data'), '2\n3\n')
        self.assertEqual(self.run_line('tail -n 0 /a/b/c/data'), '')
        self.assertEqual(self.run_line('tail "hello world"'), 'Привет\n')
        self.run_line('tail -n -2 /a/b/c/data', False)
        self.run_line('tail /a', False)
        self.run_line('tail /absent', False)

    def test_du(self):
        """du суммирует байты, включая скрытые файлы и Unicode."""
        total = sum(len(n.data) for n in self.shell.vfs.nodes.values())
        self.assertEqual(self.run_line('du -s /'), f'{total}\t/\n')
        self.assertIn('6\t/a/b/c/data', self.run_line('du -a /a'))
        self.assertNotIn('/data', self.run_line('du /a'))
        self.run_line('du -sa', False)

    def test_touch(self):
        """touch сохраняет содержимое и не создаёт отсутствующих родителей."""
        self.run_line('touch "new file"')
        self.assertEqual(self.shell.vfs.get('/new file').data, b'')
        node = self.shell.vfs.get('/a/b/c/data')
        node.mtime = 0
        self.run_line('touch /a/b/c/data')
        self.assertGreater(node.mtime, 0)
        self.assertEqual(node.data, b'1\n2\n3\n')
        self.run_line('touch -c /absent')
        self.assertNotIn('/absent', self.shell.vfs.nodes)
        self.run_line('touch /missing/new', False)
        self.run_line('touch "hello world/child"', False)

    def test_chown(self):
        """Рекурсия изменяет дерево, а :group сохраняет владельца."""
        self.run_line('chown -R alice:team /a')
        for path in self.shell.vfs.subtree('/a'):
            self.assertEqual(self.shell.vfs.get(path).owner, 'alice')
            self.assertEqual(self.shell.vfs.get(path).group, 'team')
        self.run_line('chown :other /a')
        self.assertEqual(self.shell.vfs.get('/a').owner, 'alice')
        self.assertEqual(self.shell.vfs.get('/a').group, 'other')
        self.run_line('chown 1000:1001 /a')
        self.run_line('chown bad: /a', False)
        self.run_line('chown user /missing', False)

    def test_source_unchanged(self):
        """Файлы, владельцы и mtime исходной папки не изменяются."""
        before = self.snapshot()
        self.run_line('touch /new')
        self.run_line('touch /a/b/c/data')
        self.run_line('chown -R user:group /')
        self.assertEqual(before, self.snapshot())
        fresh = VFS(self.root)
        self.assertNotIn('/new', fresh.nodes)

    def snapshot(self):
        """Фиксирует байты и метаданные физических узлов."""
        result = {}
        for path in [self.root, *self.root.rglob('*')]:
            info = path.stat()
            data = path.read_bytes() if path.is_file() else None
            result[str(path)] = (data, info.st_mtime_ns, info.st_uid,
                                 info.st_gid)
        return result

    def test_snapshot_isolation(self):
        """После загрузки чтение использует снимок, а не реальный диск."""
        (self.root / 'a/b/c/data').write_bytes(b'changed')
        self.assertEqual(self.run_line('tail /a/b/c/data'), '1\n2\n3\n')

    def test_bad_source(self):
        """Отсутствующий источник и файл вместо каталога отклоняются."""
        for source in [self.root / 'missing', self.root / 'hello world']:
            with self.assertRaises(ValueError):
                VFS(source)

    def test_symlink(self):
        """Ссылки отклоняются, в том числе ведущие вне VFS."""
        try:
            (self.root / 'link').symlink_to(self.root / 'a',
                                          target_is_directory=True)
        except (OSError, NotImplementedError):
            self.skipTest('Создание ссылок недоступно в этой ОС')
        with self.assertRaises(ValueError):
            VFS(self.root)

    def test_script_stop(self):
        """После ошибки ни одна следующая команда не выполняется."""
        script = self.root / 'start.txt'
        script.write_text('unknown\ntouch forbidden\n', encoding='utf-8')
        output = io.StringIO()
        with contextlib.redirect_stdout(output):
            self.assertFalse(run_script(self.shell, script))
        self.assertNotIn('/forbidden', self.shell.vfs.nodes)
        self.assertIn('строка 1', output.getvalue())

    def test_script_exit(self):
        """exit прекращает сценарий без ошибки."""
        script = self.root / 'start.txt'
        script.write_text('exit\ntouch forbidden\n', encoding='utf-8')
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertTrue(run_script(self.shell, script))
        self.assertNotIn('/forbidden', self.shell.vfs.nodes)

    def test_error_examples_stop(self):
        """Все ошибочные примеры останавливаются до контрольного touch."""
        project = Path(__file__).resolve().parents[1]
        for script in sorted((project / 'examples/errors').glob('*.txt')):
            with self.subTest(script=script.name):
                shell = Shell()
                shell.vfs = VFS(project / 'examples/vfs/demo')
                install(shell)
                with contextlib.redirect_stdout(io.StringIO()):
                    self.assertFalse(run_script(shell, script))
                self.assertNotIn('/MUST_NOT_EXIST', shell.vfs.nodes)

    def test_main_errors(self):
        """Ошибки VFS и чтения сценария дают ненулевой код возврата."""
        with contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(main(['--vfs', str(self.root), '--batch']), 0)
            self.assertEqual(main(['--vfs', '/absent', '--batch']), 1)
            self.assertEqual(main(['--vfs', str(self.root), '--script',
                                   '/absent', '--batch']), 1)

    def test_empty_source(self):
        """Настоящий пустой каталог является допустимой VFS."""
        with tempfile.TemporaryDirectory() as directory:
            vfs = VFS(directory)
            self.assertEqual(vfs.children('/'), [])

    def test_binary(self):
        """Двоичные данные сохраняются, tail сообщает ошибку декодирования."""
        path = self.root / 'binary'
        path.write_bytes(b'\xff\x00\xfe')
        self.shell.vfs = VFS(self.root)
        install(self.shell)
        self.assertEqual(self.shell.vfs.get('/binary').data, b'\xff\x00\xfe')
        self.run_line('tail binary', False)

    def test_real_prompt(self):
        """Приглашение использует реальные данные ОС."""
        import getpass
        import socket
        expected = f'{getpass.getuser()}@{socket.gethostname()}:/$ '
        self.assertEqual(self.shell.prompt, expected)
