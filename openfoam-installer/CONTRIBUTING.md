# Contributing

This project is currently under active testing. Bug reports should include:

- Windows version
- `wsl --version` output
- Selected OpenFOAM distribution and version
- The WSL distribution name created by the installer
- The complete error message with passwords and other sensitive values removed

Before submitting a change, run the non-destructive static checks from Windows PowerShell:

```powershell
.\tests\Test-Static.ps1
```

Do not commit generated passwords, tokens, private keys, diagnostic archives containing personal data, or exported WSL images.

