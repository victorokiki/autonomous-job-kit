"""Small helpers every command-line script shares: JSON output, exit codes, input checks."""
import json
import os
import sys

# Exit codes used across the kit
OK = 0          # done, nothing needs attention
BAD_INPUT = 1   # missing file, bad argument, unreadable input
ATTENTION = 2   # done, but something needs a look (see the JSON)
NO_LATEX = 3    # no LaTeX engine on this computer
FILE_BUSY = 4   # a file is open in another program (Excel)
MISSING_DEP = 5 # a Python package is missing
NETWORK = 6     # a download failed


def emit(obj, code=OK):
    """Print one JSON object and exit with `code`."""
    sys.stdout.write(json.dumps(obj, indent=1, ensure_ascii=False, default=str) + '\n')
    sys.stdout.flush()
    sys.exit(code)


def fail(message, code=BAD_INPUT, **extra):
    emit({'ok': False, 'error': message, **extra}, code)


def need_files(*paths):
    """Exit with a clear message if any given path (skipping None) isn't an existing file."""
    for p in paths:
        if p and not os.path.isfile(p):
            fail(f'File not found: {p}')


def need_package(module, pip_name=None):
    """Import a module or exit with the pip command that installs it."""
    try:
        return __import__(module)
    except ImportError:
        fail(f'The Python package "{pip_name or module}" is missing. Install it with: pip install {pip_name or module}',
             MISSING_DEP)


def load_json(path, default=None):
    """Read a JSON file; return `default` when it's missing or not valid JSON."""
    if not path:
        return default
    try:
        with open(path, encoding='utf-8-sig') as f:
            return json.load(f)
    except (OSError, ValueError):
        return default
