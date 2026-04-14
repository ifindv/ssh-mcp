# SSH MCP Server

[![PyPI version](https://badge.fury.io/py/ssh-mcp.svg)](https://badge.fury.io/py/ssh-mcp)
[![Python Versions](https://img.shields.io/pypi/pyversions/ssh-mcp.svg)](https://pypi.org/project/ssh-mcp/)
[![License](https://img.shields.io/pypi/l/ssh-mcp.svg)](https://github.com/your-organization/ssh-mcp/blob/main/LICENSE)

An MCP (Model Context Protocol) server that enables LLMs to interact with remote servers via SSH functionality including command execution, file upload/download, and directory listing.

## Features

- **Connection Management**: Establish and manage multiple SSH sessions
- **Command Execution**: Run shell commands on remote servers with full output capture
- **File Operations**: Upload and download files via SFTP with optional permissions
- **Directory Listing**: Browse remote directories with file metadata (size, type, timestamps)
- **Security**: Command injection prevention, proper credential handling, Pydantic validation
- **Flexible Authentication**: Support for both password and SSH key authentication

## Installation

```bash
pip install ssh-mcp
```

Or install from source:

```bash
pip install -e .
```

### Requirements

- Python 3.10 or higher
- Dependencies automatically installed via pip
  - `mcp >= 1.0.0`
  - `pydantic >= 2.0.0`
  - `paramiko >= 3.0.0`

## Usage

### Running the Server

```bash
ssh-mcp
```

Or using Python directly:

```bash
python -m ssh_mcp
```

### Testing with MCP Inspector

The MCP Inspector allows you to test the server interactively:

```bash
npx @modelcontextprotocol/inspector python -m ssh_mcp
```

### Available Tools

| Tool | Description |
|------|-------------|
| `ssh_connect` | Establish SSH connection to remote server |
| `ssh_status` | Check status of SSH sessions |
| `ssh_execute` | Execute commands on remote server |
| `ssh_upload_file` | Upload files to remote server |
| `ssh_download_file` | Download files from remote server |
| `ssh_list_files` | List files in remote directory |
| `ssh_disconnect` | Close SSH connection |

### Example Workflow

#### 1. Connect to a server

Using password authentication:
```python
{
  "host": "192.168.1.100",
  "port": 22,
  "username": "admin",
  "password": "your_password"
}
```

Using SSH key authentication:
```python
{
  "host": "192.168.1.100",
  "port": 22,
  "username": "admin",
  "private_key_path": "/home/user/.ssh/id_rsa",
  "private_key_password": "key_passphrase"  # optional for encrypted keys
}
```

#### 2. Execute a command

```python
{
  "session_id": "admin@192.168.1.100:22",
  "command": "ls -la /var/log",
  "working_directory": "/var/log",  # optional
  "response_format": "markdown"  // "json" for machine-readable output
}
```

#### 3. Upload a file

```python
{
  "session_id": "admin@192.168.1.100:22",
  "local_path": "./config.json",
  "remote_path": "/tmp/config.json",
  "file_mode": 511  // 0o644 in octal
}
```

#### 4. Download a file

```python
{
  "session_id": "admin@192.168.1.100:22",
  "remote_path": "/var/log/syslog",
  "local_path": "./syslog",
  "overwrite": false
}
```

#### 5. List a directory

```python
{
  "session_id": "admin@192.168.1.100:22",
  "remote_path": "/tmp",
  "show_hidden": false,
  "response_format": "markdown"
}
```

#### 6. Disconnect

```python
{
  "session_id": "admin@192.168.1.100:22"
}
```

## Configuration

### Session Management

Multiple concurrent SSH sessions are supported. Each session is identified by a `session_id`:
- Auto-generated as `{username}@{host}:{port}` if not specified
- Can be explicitly provided for custom naming
- Sessions persist as long as the server is running

### Authentication Methods

The server supports two authentication methods:

1. **Password authentication**:
   - Provide `password` parameter in `ssh_connect`
   - Suitable for quick testing or environments where keys are not available

2. **SSH Key authentication** (recommended for production):
   - Provide `private_key_path` parameter pointing to your private key file
   - Optionally provide `private_key_password` for encrypted keys
   - More secure than password-based authentication

### Response Formats

Tools that return structured data support two formats:

- **markdown** (default): Human-readable output with formatting
- **json**: Machine-readable structured data

## Development

### Setting up the development environment

```bash
# Clone the repository
git clone https://github.com/your-organization/ssh-mcp.git
cd ssh-mcp

# Install in development mode
pip install -e ".[dev]"

# Run tests (when available)
pytest

# Format code
black ssh_mcp/

# Type checking
mypy ssh_mcp/
```

### Code Style

This project uses:
- **Black** for code formatting (line length: 100)
- **MyPy** for static type checking
- **PEP 8** for style guidelines

## Security Considerations

- **Command injection prevention**: Invalid characters are filtered from command inputs
- **Host key verification**: Uses `AutoAddPolicy` by default. For production environments, configure proper host key verification
- **Credential handling**: Credentials are passed via parameters and are not stored persistently
- **Input validation**: All inputs are validated using Pydantic models
- **Sensitive data**: Passwords and private key passwords are marked as sensitive in the schema

## Troubleshooting

### Connection Refused

- Verify SSH service is running on the target server
- Check firewall settings and network connectivity
- Ensure the correct port is specified (default: 22)

### Authentication Failed

- Verify username and password/SSH key are correct
- Check that the private key file exists and has correct permissions
- Ensure the SSH key is added to the server's `~/.ssh/authorized_keys` file

### Timeout Errors

- Check network connectivity and latency
- Increase the `timeout` parameter value
- Verify that the server is responsive and not overloaded

### Permission Denied

- Ensure user has appropriate permissions on the remote server
- Check file and directory permissions for SFTP operations
- Verify SSH key permissions (typically 600 for private keys)

## Contributing

Contributions are welcome! Please read our contributing guidelines and submit pull requests to our repository.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Support

- **Issues**: [GitHub Issues](https://github.com/your-organization/ssh-mcp/issues)
- **Documentation**: [GitHub Wiki](https://github.com/your-organization/ssh-mcp/wiki)

## Acknowledgments

- Built with [MCP SDK](https://github.com/modelcontextprotocol/python-sdk)
- SSH functionality powered by [Paramiko](https://www.paramiko.org/)
- Data validation with [Pydantic](https://docs.pydantic.dev/)
