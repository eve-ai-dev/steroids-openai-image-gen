#!/usr/bin/env python3
"""Run upstream admission without installing dependencies or sending messages.

Usage: PYTHONPATH=<verified-hermes-checkout>:/opt/hermes python .agents/validate_admission.py
Example: see .agents/validation.md for the canonical checkout and invocation.
"""
import json
from pathlib import Path
from hermes_cli.plugin_validate import validate_plugin_dir


def main():
    root = Path(__file__).resolve().parents[1]
    report = validate_plugin_dir(root)
    data = report.to_dict()
    (root / 'outputs').mkdir(exist_ok=True)
    (root / 'outputs/admission.json').write_text(json.dumps(data, indent=2) + '\n')
    print(json.dumps(data, indent=2))
    return report.exit_code


if __name__ == '__main__':
    raise SystemExit(main())
