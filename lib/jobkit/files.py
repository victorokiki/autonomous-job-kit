"""File handling rules: never delete a user's file, keep names safe on every operating system."""
import datetime as dt
import os
import re
import shutil

_BAD_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')


def stamp():
    return dt.datetime.now().strftime('%Y-%m-%d_%H%M%S')


def move_to_old(path):
    """Move an existing file (or folder) into an _old/ folder beside it, with the date and time added to its name.

    Returns the new path, or None when there was nothing to move. Nothing is ever deleted."""
    if not os.path.exists(path):
        return None
    folder = os.path.join(os.path.dirname(os.path.abspath(path)), '_old')
    os.makedirs(folder, exist_ok=True)
    base, ext = os.path.splitext(os.path.basename(path.rstrip('/\\')))
    dest = os.path.join(folder, f'{base} {stamp()}{ext}')
    n = 2
    while os.path.exists(dest):
        dest = os.path.join(folder, f'{base} {stamp()} ({n}){ext}')
        n += 1
    shutil.move(path, dest)
    return dest


def safe_name(text, limit=120):
    """A file or folder name that works on Windows, macOS and Linux."""
    name = _BAD_CHARS.sub(' ', str(text or '')).strip().strip('.')
    name = re.sub(r'\s+', ' ', name)
    return name[:limit].rstrip() or 'untitled'


def write_text(path, text):
    """Write a text file (UTF-8), moving any existing file at that path into _old/ first."""
    moved = move_to_old(path)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(text)
    return moved


def upload_copy(path, folder=None):
    """Copy a file into a folder whose path has no spaces (the Claude in Chrome upload tool can reject paths with
    spaces). Default folder: ~/job-uploads. Returns the copy's path."""
    folder = folder or os.path.join(os.path.expanduser('~'), 'job-uploads')
    if ' ' in folder:
        raise ValueError('the uploads folder path must not contain spaces')
    os.makedirs(folder, exist_ok=True)
    dest = os.path.join(folder, os.path.basename(path).replace(' ', '_'))
    if os.path.exists(dest):
        move_to_old(dest)
    shutil.copy2(path, dest)
    return dest
