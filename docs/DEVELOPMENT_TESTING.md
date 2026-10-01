# RF Finder Development Testing

RF Finder uses GitHub Actions as continuous integration (CI) and keeps the development test path reproducible on a developer machine.

## Local development test

From the repository root:

```powershell
.\.venv\Scripts\activate.bat
python -m compileall -q app
python -m pytest -q
```

For a faster syntax-only check:

```powershell
python -m compileall -q app
```

## Continuous integration

The `RF Finder Tests` workflow now runs on:

- every push to every branch
- every pull request targeting `main`
- manual `workflow_dispatch`

The CI matrix validates Python 3.11, 3.12, 3.13, and 3.14.

Each CI run:

1. installs the pinned project dependency ranges from `requirements.txt`
2. compiles the application
3. runs the blocking flake8 checks
4. runs the complete pytest suite

## Development workflow

Recommended workflow:

1. Create a feature branch.
2. Make a small change.
3. Run the local compile and pytest commands.
4. Push the branch.
5. Let GitHub Actions validate the branch automatically.
6. Open a pull request into `main` after CI passes.

This keeps development builds/test changes separate from production/release artifacts.
