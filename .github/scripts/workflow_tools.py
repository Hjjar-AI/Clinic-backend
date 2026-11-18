"""Validate workflow YAML, immutable references and Python syntax without running job code."""
import argparse
import ast
from pathlib import Path
import re


EXTERNAL_USE = re.compile(r'[\w.-]+/[\w./-]+@[0-9a-fA-F]{40}')


def validate(root):
    import yaml

    class Loader(yaml.SafeLoader):
        def construct_mapping(self, node, deep=False):
            keys = [self.construct_object(key, deep=False) for key, _ in node.value]
            if len(set(keys)) != len(keys):
                raise ValueError(f'duplicate YAML key at {node.start_mark}')
            return super().construct_mapping(node, deep=deep)

    files = sorted((root / '.github/workflows').glob('*.y*ml'))
    actions = sorted((root / '.github/actions').glob('**/action.y*ml'))
    python_blocks = 0
    references = 0

    def walk(value, file):
        nonlocal python_blocks, references
        if isinstance(value, dict):
            use = value.get('uses')
            if use is not None:
                if not isinstance(use, str) or not (use.startswith('./') or EXTERNAL_USE.fullmatch(use)):
                    raise ValueError(f'{file}: external uses must pin a full commit SHA: {use}')
                references += 1
            if value.get('shell') == 'python' and 'run' in value:
                ast.parse(value['run'], filename=str(file))
                python_blocks += 1
            for child in value.values():
                walk(child, file)
        elif isinstance(value, list):
            for child in value:
                walk(child, file)

    for file in files + actions:
        data = yaml.load(file.read_text(encoding='utf-8'), Loader=Loader)
        if not isinstance(data, dict):
            raise ValueError(f'{file}: expected a YAML mapping')
        if file in actions:
            if not data.get('name') or not data.get('description'):
                raise ValueError(f'{file}: action name and description are required')
            runs = data.get('runs', {})
            if runs.get('using') != 'composite' or not isinstance(runs.get('steps'), list):
                raise ValueError(f'{file}: expected composite steps')
            for step in runs['steps']:
                if ('run' in step) == ('uses' in step) or ('run' in step and not step.get('shell')):
                    raise ValueError(f'{file}: each composite step needs uses or run with shell')
        walk(data, file)
    scripts = sorted((root / '.github/scripts').glob('*.py'))
    for script in scripts:
        ast.parse(script.read_text(encoding='utf-8'), filename=str(script))
    print(f'Validated {len(files)} workflows, {len(actions)} composite actions, '
          f'{references} pinned/local references and {python_blocks} Python blocks')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--validate', action='store_true', required=True)
    parser.add_argument('--root', type=Path, default=Path('.'))
    args = parser.parse_args()
    validate(args.root)


if __name__ == '__main__':
    main()
