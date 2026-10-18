# Security

Design Finder runs fully offline. It makes no network connections, uploads nothing, and never saves screen captures. The only program it starts is Windows' own `explorer.exe` (for **Open folder**), called by full path without a shell.

## Reporting a problem

Please report security issues **privately**: open this repository's **Security** tab and choose **Report a vulnerability**. Don't open a public issue for them.

## What is checked

On every push, CI runs the test suite, `bandit` (static analysis) and `pip-audit` (known vulnerabilities in dependencies). Dependabot proposes dependency updates every week. To check locally:

```powershell
pip install -e ".[dev]"
bandit -q -r src scripts packaging
pip-audit --skip-editable
```

## Notes for users

- `DesignFinder.exe` isn't code-signed, so Windows SmartScreen asks for confirmation on the first run. Only use an exe that you built yourself from this repository, or that came from someone you trust.
- The index (`index.db`) holds file paths and numeric fingerprints, not images. It stays next to the exe on your own computer.
