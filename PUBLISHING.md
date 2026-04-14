# Publishing to PyPI

This guide explains how to publish `ssh-mcp` to PyPI.

## Prerequisites

1. **PyPI account**: Sign up at https://pypi.org/account/register/
2. **API Token**: Generate an API token at https://pypi.org/manage/account/token/
   - Scope: "Entire account" or specific project
   - Save the token - you won't be able to see it again

3. **Install build tools**:
   ```bash
   pip install build twine
   ```

## Publishing Steps

### 1. Update Metadata

Before publishing, ensure `pyproject.toml` has correct metadata:
- Version number (increment if releasing a new version)
- Author information
- Repository URLs
- If this is your first release, update the GitHub URLs in `pyproject.toml` and `README.md`

### 2. Clean Build Artifacts

```bash
# Remove old build artifacts
rm -rf dist/ build/ *.egg-info
```

### 3. Build the Package

```bash
python -m build
```

This creates `dist/` directory with:
- `ssh_mcp-x.x.x-py3-none-any.whl` - wheel file
- `ssh_mcp-x.x.x.tar.gz` - source distribution

### 4. Check the Package (Recommended)

```bash
twine check dist/*
```

This validates the package metadata.

### 5. Upload to TestPyPI (Optional)

TestPyPI is a separate instance of PyPI for testing:

```bash
twine upload --repository testpypi dist/*
```

Install from TestPyPI:
```bash
pip install --index-url https://test.pypi.org/simple/ ssh-mcp
```

### 6. Upload to PyPI

```bash
twine upload dist/*
```

You'll be prompted for:
- Username: `__token__`
- Password: your PyPI API token

### 7. Verify

Visit https://pypi.org/project/ssh-mcp/ to verify the package is published.

## Version Management

Use semantic versioning for releases:

- `MAJOR.MINOR.PATCH`
  - Increment MAJOR for incompatible changes
  - Increment MINOR for backwards-compatible features
  - Increment PATCH for backwards-compatible bug fixes

## Common Issues

### "File already exists"

If you get this error, increment the version number in `pyproject.toml`.

### "Username or password invalid"

When using API tokens:
- Username: always `__token__`
- Password: your API token (not your PyPI password)

### Metadata validation errors

Ensure all fields in `pyproject.toml` are filled correctly, especially:
- `version` (must be unique for each release)
- `license`
- `authors` with email
- `readme` file exists

## Continuous Publishing

For automated publishing, consider using GitHub Actions. See `.github/workflows/publish.yml` (if created).

## Security Notes

- Never commit API tokens to git
- Use GitHub secrets for CI/CD
- Consider using trusted publishers for GitHub Actions instead of tokens
