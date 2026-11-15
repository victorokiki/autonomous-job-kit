"""Job Kit for Claude: shared library for the kit's command-line scripts.

The scripts in each skill's scripts/ folder import from here. In the repository the package lives in lib/jobkit;
install.sh / install.ps1 copy it into every installed skill's scripts/ folder, so each skill works on its own.

Every script prints exactly one JSON object on stdout (see jobkit.cli.emit) and never deletes a user's file: a file
that would be replaced is moved into an _old/ folder beside it first (jobkit.files.move_to_old).
"""
__version__ = '2.0.0'
