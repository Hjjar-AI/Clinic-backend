"""Launcher configuration/process behavior; no Django or clinic storage access."""
from contextlib import contextmanager
import os
from pathlib import Path
import signal
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch

import launch


class LauncherTests(unittest.TestCase):
    def setUp(self):
        self.workspace = tempfile.TemporaryDirectory(prefix='clinic-launcher-')
        self.addCleanup(self.workspace.cleanup)
        self.root = Path(self.workspace.name) / 'backend'
        self.root.mkdir()
        self.frontend = self.root.parent / 'frontend'
        self.frontend.mkdir()
        self.template = 'DJANGO_SECRET_KEY=\nBACKUP_HMAC_KEY=\nALLOW_DEMO_DATA=false\n'
        (self.root / '.env.example').write_text(self.template)
        (self.root / '.env').write_text('DJANGO_SETTINGS_MODULE=config.settings.development\n')

    def config(self, text='', environ=None, **kwargs):
        (self.root / '.env').write_text(text)
        with patch('launch.executable', side_effect=lambda value, candidates, root, label: value or label.lower()):
            return launch.configuration(self.root, environ or {}, **kwargs)

    def test_configure_creates_distinct_private_keys_without_schema_or_data(self):
        (self.root / '.env').unlink()
        with patch('builtins.print') as output:
            self.assertTrue(launch.configure(self.root))
        content = (self.root / '.env').read_text()
        values = dict(line.split('=', 1) for line in content.splitlines())
        self.assertEqual(len(values['DJANGO_SECRET_KEY']), 64)
        self.assertNotEqual(values['DJANGO_SECRET_KEY'], values['BACKUP_HMAC_KEY'])
        self.assertNotIn(values['DJANGO_SECRET_KEY'], str(output.call_args_list))
        if os.name == 'posix':
            self.assertEqual((self.root / '.env').stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.root / 'data').exists())
        self.assertFalse((self.root / 'migrations').exists())

    def test_configure_never_replaces_existing_bytes_or_keys(self):
        before = (self.root / '.env').read_bytes()
        stamp = (self.root / '.env').stat().st_mtime_ns
        with patch('builtins.print'):
            self.assertFalse(launch.configure(self.root))
        self.assertEqual((self.root / '.env').read_bytes(), before)
        self.assertEqual((self.root / '.env').stat().st_mtime_ns, stamp)

    def test_invalid_template_does_not_create_partial_environment(self):
        (self.root / '.env').unlink()
        (self.root / '.env.example').write_text('DJANGO_SECRET_KEY=\n')
        with self.assertRaises(launch.LaunchError):
            launch.configure(self.root)
        self.assertFalse((self.root / '.env').exists())

    def test_custom_ports_keep_proxy_csrf_and_local_hosts_in_sync(self):
        config = self.config('CLINIC_BACKEND_PORT=5020\nCLINIC_FRONTEND_PORT=5175\n'
            'CSRF_TRUSTED_ORIGINS=https://existing.invalid\n')
        self.assertEqual(config.env['VITE_BACKEND_URL'], 'http://127.0.0.1:5020')
        self.assertEqual(config.env['VITE_API_BASE_URL'], '/api/v1')
        self.assertIn('http://127.0.0.1:5175', config.env['CSRF_TRUSTED_ORIGINS'].split(','))
        self.assertIn('https://existing.invalid', config.env['CSRF_TRUSTED_ORIGINS'].split(','))
        self.assertEqual(config.env['DJANGO_ALLOWED_HOSTS'], '127.0.0.1,localhost')

    def test_quotes_comments_exports_and_shell_precedence(self):
        config = self.config("export CLINIC_PYTHON='/Synthetic path/python' # chosen environment\n"
            'CLINIC_BACKEND_PORT=5019 # local API\nCLINIC_FRONTEND_PORT=5173\n'
            'DATABASE_PASSWORD="private-${VALUE}"\n', {'CLINIC_BACKEND_PORT': '5022'})
        self.assertEqual(config.python, '/Synthetic path/python')
        self.assertEqual(config.backend_port, 5022)
        self.assertNotIn('DATABASE_PASSWORD', config.env)

    def test_refuses_production_profile(self):
        for environ in ({}, {'DJANGO_SETTINGS_MODULE': 'config.settings.production'}):
            with self.subTest(environ=environ), self.assertRaises(launch.LaunchError):
                self.config('DJANGO_SETTINGS_MODULE=config.settings.production\n', environ)

    def test_invalid_equal_or_out_of_range_ports_are_rejected(self):
        for value in ('0', '-1', '65536', 'true', '1.5', '5019;anything'):
            with self.subTest(value=value), self.assertRaises(launch.LaunchError):
                self.config(f'CLINIC_BACKEND_PORT={value}\n')
        with self.assertRaises(launch.LaunchError):
            self.config('CLINIC_BACKEND_PORT=5173\n')

    def test_invalid_boolean_quotes_and_expansion_are_rejected(self):
        for text in ('CLINIC_OPEN_BROWSER=yes\n', 'CLINIC_NODE="unclosed\n', 'CLINIC_PYTHON=${RUNTIME}/python\n'):
            with self.subTest(text=text), self.assertRaises(launch.LaunchError):
                self.config(text)

    def test_browser_can_be_disabled_in_environment_or_cli(self):
        self.assertFalse(self.config('CLINIC_OPEN_BROWSER=false\n').open_browser)
        self.assertFalse(self.config(no_browser=True).open_browser)

    def test_explicit_executable_path_with_spaces_stays_one_path(self):
        filename = self.root / 'Synthetic runtime' / 'python'
        filename.parent.mkdir()
        filename.write_text('synthetic')
        filename.chmod(0o700)
        with patch('launch.shutil.which', return_value=None):
            self.assertEqual(launch.executable(str(filename), [], self.root, 'Python'), str(filename))

    @contextmanager
    def preflight_tools(self, config, outputs=None):
        vite = config.frontend / 'node_modules/vite/bin/vite.js'
        vite.parent.mkdir(parents=True, exist_ok=True)
        vite.write_text('// synthetic fixture')
        outputs = outputs if outputs is not None else ['[3,12]', '[]', 'true', 'v24.21.0']
        with patch('launch.checked_output', side_effect=outputs), patch('launch.require_free_port') as ports, \
                patch('launch.subprocess.run', return_value=subprocess.CompletedProcess([], 0)) as command:
            yield ports, command

    def test_preflight_checks_tools_ports_native_runtime_without_install_or_schema_jobs(self):
        config = self.config()
        with self.preflight_tools(config) as (ports, command):
            launch.preflight(config)
        self.assertEqual([call.args[0] for call in ports.call_args_list], [5019, 5173])
        self.assertEqual(command.call_args.args[0], ['python', '-B', 'manage.py', 'check_runtime', '--render-pdf'])

    def test_preflight_rejects_unsupported_python_missing_packages_or_keys(self):
        for outputs in (['[3,14]'], ['[3,12]', '["django"]'], ['[3,12]', 'unexpected'], ['[3,12]', '[]', 'false']):
            with self.subTest(outputs=outputs):
                config = self.config()
                with self.preflight_tools(config, outputs), self.assertRaises(launch.LaunchError):
                    launch.preflight(config)

    def test_preflight_rejects_unsupported_node_versions(self):
        for version in ('v22.17.0', 'v23.1.0', 'v24.11.0', 'unexpected'):
            with self.subTest(version=version):
                config = self.config()
                with self.preflight_tools(config, ['[3,12]', '[]', 'true', version]), self.assertRaises(launch.LaunchError):
                    launch.preflight(config)

    def test_occupied_port_error_does_not_stop_existing_owner(self):
        with patch('launch.socket.socket') as socket_factory:
            socket_factory.return_value.__enter__.return_value.bind.side_effect = OSError('Synthetic occupied port')
            with self.assertRaisesRegex(launch.LaunchError, 'unavailable'):
                launch.require_free_port(5019)

    def processes(self):
        return [Mock(pid=10001, poll=Mock(return_value=None)), Mock(pid=10002, poll=Mock(return_value=None))]

    def test_ctrl_c_stops_both_owned_servers_and_opens_browser_after_readiness(self):
        config = self.config()
        backend, frontend = self.processes()
        with patch('launch.spawn', side_effect=[backend, frontend]) as spawn, patch('launch.stop') as stop, \
                patch('launch.ready', return_value=True), patch('launch.webbrowser.open') as browser, \
                patch('launch.time.sleep', side_effect=KeyboardInterrupt), patch('builtins.print'):
            launch.run_servers(config)
        self.assertEqual([call.args[0] for call in stop.call_args_list], [frontend, backend])
        browser.assert_called_once_with('http://127.0.0.1:5173')
        self.assertIn('--strictPort', spawn.call_args_list[1].args[0])
        self.assertEqual(spawn.call_args_list[1].args[0][0], 'node')

    def test_partial_start_failure_cleans_up_started_server(self):
        config = self.config()
        backend = self.processes()[0]
        with patch('launch.spawn', side_effect=[backend, OSError('Synthetic second process failure')]), patch('launch.stop') as stop:
            with self.assertRaises(OSError):
                launch.run_servers(config)
        stop.assert_called_once_with(backend)

    def test_child_exit_stops_sibling_without_opening_browser(self):
        config = self.config()
        backend, frontend = self.processes()
        backend.poll.return_value = 1
        with patch('launch.spawn', side_effect=[backend, frontend]), patch('launch.stop') as stop, patch('launch.webbrowser.open') as browser:
            with self.assertRaisesRegex(launch.LaunchError, 'Backend stopped'):
                launch.run_servers(config)
        self.assertEqual(stop.call_count, 2)
        browser.assert_not_called()

    def test_timeout_stops_both_servers(self):
        config = self.config()
        with patch('launch.spawn', side_effect=self.processes()), patch('launch.stop') as stop, \
                patch('launch.ready', return_value=False), patch('launch.time.monotonic', side_effect=[0, 2]):
            with self.assertRaisesRegex(launch.LaunchError, 'timed out'):
                launch.run_servers(config, timeout=1)
        self.assertEqual(stop.call_count, 2)

    def test_browser_failure_does_not_stop_a_healthy_start(self):
        config = self.config()
        with patch('launch.spawn', side_effect=self.processes()), patch('launch.stop'), patch('launch.ready', return_value=True), \
                patch('launch.webbrowser.open', side_effect=launch.webbrowser.Error()), \
                patch('launch.time.sleep', side_effect=KeyboardInterrupt), patch('builtins.print'):
            launch.run_servers(config)

    @unittest.skipUnless(os.name == 'posix', 'POSIX owned process groups')
    def test_stop_targets_only_the_owned_process_group(self):
        process = Mock(pid=12345)
        with patch('launch.os.killpg') as kill:
            launch.stop(process)
        self.assertEqual([call.args for call in kill.call_args_list], [(12345, signal.SIGTERM), (12345, signal.SIGKILL)])

    def test_windows_spawn_uses_a_new_process_group_without_shell(self):
        with patch('launch.os.name', 'nt'), patch.object(subprocess, 'CREATE_NEW_PROCESS_GROUP', 512, create=True), \
                patch('launch.subprocess.Popen') as popen:
            launch.spawn(['synthetic.exe', 'argument'], 'synthetic-directory', {})
        self.assertEqual(popen.call_args.kwargs['creationflags'], 512)
        self.assertNotIn('shell', popen.call_args.kwargs)

    def test_windows_cleanup_targets_only_the_owned_pid_tree(self):
        process = Mock(pid=12345, poll=Mock(return_value=None))
        with patch('launch.os.name', 'nt'), patch('launch.subprocess.run') as command:
            launch.stop(process)
        self.assertEqual(command.call_args.args[0], ['taskkill', '/PID', '12345', '/T', '/F'])
        process.wait.assert_called_once_with(timeout=10)

    def test_check_command_does_not_start_servers_or_replace_environment(self):
        config = self.config()
        before = (self.root / '.env').read_bytes()
        with patch('launch.ROOT', self.root), patch('launch.configuration', return_value=config), \
                patch('launch.preflight'), patch('launch.run_servers') as run, patch('builtins.print'):
            self.assertEqual(launch.main(['check']), 0)
        run.assert_not_called()
        self.assertEqual((self.root / '.env').read_bytes(), before)

    def test_child_errors_do_not_echo_private_command_output(self):
        with patch('launch.subprocess.run', side_effect=subprocess.CalledProcessError(1, [], output='synthetic-private-value')):
            with self.assertRaises(launch.LaunchError) as error:
                launch.checked_output(['synthetic'], cwd=self.root, env={})
        self.assertNotIn('synthetic-private-value', str(error.exception))
