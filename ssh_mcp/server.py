#!/usr/bin/env python3
"""
SSH MCP Server.

This server provides tools to interact with remote servers via SSH, including command execution,
file upload/download, and directory listing capabilities.
"""

from typing import Optional, Dict, Any
from enum import Enum

import paramiko
from pathlib import Path
from pydantic import BaseModel, Field, field_validator, ConfigDict
from mcp.server.fastmcp import FastMCP

# Initialize the MCP server
mcp = FastMCP("ssh_mcp")

# Database of active SSH connections
_ssh_connections: Dict[str, paramiko.SSHClient] = {}

# Constants
DEFAULT_SSH_PORT = 22
DEFAULT_TIMEOUT = 30


class ResponseFormat(str, Enum):
    """Output format for tool responses."""
    MARKDOWN = "markdown"
    JSON = "json"


# Pydantic Models for Input Validation


class ConnectInput(BaseModel):
    """Input model for SSH connection."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    host: str = Field(..., description="Remote server hostname or IP address", min_length=1)
    port: int = Field(default=DEFAULT_SSH_PORT, description="SSH port number", ge=1, le=65535)
    username: str = Field(..., description="SSH username", min_length=1)
    password: Optional[str] = Field(
        default=None,
        description="SSH password (alternative to private_key)",
        json_schema_extra={"sensitive": True}
    )
    private_key_path: Optional[str] = Field(
        default=None,
        description="Path to private key file for authentication"
    )
    private_key_password: Optional[str] = Field(
        default=None,
        description="Password for private key (if encrypted)",
        json_schema_extra={"sensitive": True}
    )
    timeout: int = Field(default=DEFAULT_TIMEOUT, description="Connection timeout in seconds", ge=1, le=300)
    session_id: Optional[str] = Field(
        default=None,
        description="Session identifier for this connection. Auto-generated if omitted",
        min_length=1
    )

    @field_validator('private_key_path')
    @classmethod
    def validate_private_key_path(cls, v: Optional[str]) -> Optional[str]:
        """Validate that the private key file exists."""
        if v is not None:
            path = Path(v)
            if not path.exists():
                raise ValueError(f"Private key file not found: {v}")
            if not path.is_file():
                raise ValueError(f"Private key path is not a file: {v}")
        return v


class ExecuteInput(BaseModel):
    """Input model for remote command execution."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    session_id: str = Field(..., description="SSH session identifier from ssh_connect", min_length=1)
    command: str = Field(..., description="Command to execute on remote server", min_length=1)
    working_directory: Optional[str] = Field(
        default=None,
        description="Working directory for command execution"
    )
    timeout: int = Field(default=DEFAULT_TIMEOUT, description="Execution timeout in seconds", ge=1, le=600)
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )

    @field_validator('command')
    @classmethod
    def validate_command(cls, v: str) -> str:
        """Validate command and prevent injection."""
        # Basic command injection prevention
        dangerous_chars = ['\x00', '\r']
        for char in dangerous_chars:
            if char in v:
                raise ValueError(f"Command contains invalid character: {repr(char)}")
        return v.strip()


class UploadFileInput(BaseModel):
    """Input model for file upload."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    session_id: str = Field(..., description="SSH session identifier from ssh_connect", min_length=1)
    local_path: str = Field(..., description="Path to local file to upload", min_length=1)
    remote_path: str = Field(..., description="Destination path on remote server", min_length=1)
    file_mode: int = Field(
        default=0o644,
        description="File permissions mode (octal), default 0o644",
        ge=0o0,
        le=0o777
    )

    @field_validator('local_path')
    @classmethod
    def validate_local_path(cls, v: str) -> str:
        """Validate that the local file exists."""
        path = Path(v)
        if not path.exists():
            raise ValueError(f"Local file not found: {v}")
        if not path.is_file():
            raise ValueError(f"Local path is not a file: {v}")
        return str(path.absolute())


class DownloadFileInput(BaseModel):
    """Input model for file download."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    session_id: str = Field(..., description="SSH session identifier from ssh_connect", min_length=1)
    remote_path: str = Field(..., description="Path to remote file to download", min_length=1)
    local_path: str = Field(..., description="Destination path for downloaded file", min_length=1)
    overwrite: bool = Field(default=False, description="Overwrite local file if it exists")

    @field_validator('local_path')
    @classmethod
    def validate_local_path(cls, v: str) -> str:
        """Validate that local path is not a directory."""
        path = Path(v)
        if path.exists() and path.is_dir():
            raise ValueError(f"Local path is a directory, not a file: {v}")
        return str(path.absolute())


class ListFilesInput(BaseModel):
    """Input model for directory listing."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    session_id: str = Field(..., description="SSH session identifier from ssh_connect", min_length=1)
    remote_path: str = Field(..., description="Path to remote directory to list", min_length=1)
    show_hidden: bool = Field(default=False, description="Show hidden files (starting with .)")
    response_format: ResponseFormat = Field(
        default=ResponseFormat.MARKDOWN,
        description="Output format: 'markdown' for human-readable or 'json' for machine-readable"
    )


class DisconnectInput(BaseModel):
    """Input model for SSH disconnection."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    session_id: str = Field(..., description="SSH session identifier to close", min_length=1)


class StatusInput(BaseModel):
    """Input model for connection status check."""
    model_config = ConfigDict(
        str_strip_whitespace=True,
        validate_assignment=True,
        extra='forbid'
    )

    session_id: Optional[str] = Field(
        default=None,
        description="SSH session identifier. If omitted, lists all active sessions"
    )


# Shared utility functions


def _format_command_result(stdout: str, stderr: str, exit_code: int) -> Dict[str, Any]:
    """Format command execution result into structured data."""
    return {
        "exit_code": exit_code,
        "stdout": stdout,
        "stderr": stderr,
        "success": exit_code == 0
    }


def _format_file_attrs(attrs: paramiko.SFTPAttributes) -> Dict[str, Any]:
    """Format SFTP file attributes into readable data."""
    file_type = "unknown"
    if attrs.st_mode is not None:
        import stat
        if stat.S_ISDIR(attrs.st_mode):
            file_type = "directory"
        elif stat.S_ISREG(attrs.st_mode):
            file_type = "file"
        elif stat.S_ISLNK(attrs.st_mode):
            file_type = "symlink"

    return {
        "filename": attrs.filename if hasattr(attrs, 'filename') else "",
        "size": attrs.st_size,
        "modified": attrs.st_mtime if attrs.st_mtime else None,
        "permissions": oct(attrs.st_mode) if attrs.st_mode else None,
        "type": file_type
    }


def _format_file_list_markdown(files: list, remote_path: str) -> str:
    """Format file list as markdown."""
    lines = [f"# Directory Listing: {remote_path}", ""]
    lines.append(f"Total items: {len(files)}")
    lines.append("")

    # Group by type
    directories = [f for f in files if f['type'] == 'directory']
    files_list = [f for f in files if f['type'] == 'file']
    other = [f for f in files if f['type'] not in ('directory', 'file')]

    if directories:
        lines.append("## Directories")
        for f in directories:
            lines.append(f"- 📁 `{f['filename']}`")
        lines.append("")

    if files_list:
        lines.append("## Files")
        for f in files_list:
            size_str = _format_size(f['size'])
            lines.append(f"- 📄 `{f['filename']}` ({size_str})")
        lines.append("")

    if other:
        lines.append("## Other")
        for f in other:
            icon = "🔗" if f['type'] == 'symlink' else "❓"
            lines.append(f"- {icon} `{f['filename']}` ({f['type']})")
        lines.append("")

    return "\n".join(lines)


def _format_size(size: Optional[int]) -> str:
    """Format file size in human-readable format."""
    if size is None:
        return "N/A"
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024:
            return f"{size:.1f} {unit}"
        size /= 1024
    return f"{size:.1f} PB"


def _handle_ssh_error(e: Exception) -> str:
    """Consistent error formatting for SSH operations."""
    if isinstance(e, paramiko.AuthenticationException):
        return "Error: SSH authentication failed. Check username, password, or private key."
    elif isinstance(e, paramiko.SSHException):
        if "Could not establish" in str(e):
            return "Error: Could not establish SSH connection. Check host and port, and ensure SSH service is running."
        return f"Error: SSH protocol error: {str(e)}"
    elif isinstance(e, paramiko.BadHostKeyException):
        return "Error: SSH host key verification failed. This may indicate a security issue."
    elif isinstance(e, FileNotFoundError):
        return f"Error: File not found: {str(e)}"
    elif isinstance(e, PermissionError):
        return f"Error: Permission denied: {str(e)}"
    elif isinstance(e, TimeoutError):
        return "Error: Operation timed out. Check network connection or increase timeout value."
    elif isinstance(e, KeyError):
        return f"Error: Session not found. The session ID is invalid or the connection has been closed."
    return f"Error: Unexpected error: {type(e).__name__}: {str(e)}"


# Tool definitions


@mcp.tool(
    name="ssh_connect",
    annotations={
        "title": "Connect to SSH Server",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def ssh_connect(params: ConnectInput) -> str:
    """
    Establish an SSH connection to a remote server.

    This tool creates a new SSH session that can be used for subsequent operations
    like command execution, file upload/download, and directory listing.

    Args:
        params (ConnectInput): Validated input parameters containing:
            - host (str): Remote server hostname or IP address (e.g., "192.168.1.100", "server.example.com")
            - port (int): SSH port number, default 22, range 1-65535
            - username (str): SSH username for authentication
            - password (Optional[str]): Password for authentication (alternative to private_key_path)
            - private_key_path (Optional[str]): Path to SSH private key file (alternative to password)
            - private_key_password (Optional[str]): Password for encrypted private key
            - timeout (int): Connection timeout in seconds, default 30, range 1-300
            - session_id (Optional[str]): Session identifier, auto-generated if omitted

    Returns:
        str: Session ID for the established connection or error message

    Examples:
        - Use when: "Connect to server 192.168.1.100 with username admin" -> params with host="192.168.1.100", username="admin"
        - Use when: "Connect using SSH key" -> params with private_key_path="/path/to/key"
        - Don't use when: Session already exists (use ssh_status to check)
        - Don't use when: Need to execute multiple commands to different servers (create separate sessions)

    Error Handling:
        - Returns error if authentication fails (check credentials)
        - Returns error if host is unreachable (check network)
        - Returns error if port is invalid or service not running
    """
    try:
        client = paramiko.SSHClient()
        client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

        # Generate session ID if not provided
        session_id = params.session_id or f"{params.username}@{params.host}:{params.port}"

        # Prepare authentication
        if params.private_key_path:
            private_key = paramiko.RSAKey.from_private_key_file(
                params.private_key_path,
                password=params.private_key_password
            )
            client.connect(
                hostname=params.host,
                port=params.port,
                username=params.username,
                pkey=private_key,
                timeout=params.timeout,
                allow_agent=False,
                look_for_keys=False
            )
        else:
            if not params.password:
                return "Error: Either password or private_key_path must be provided for authentication."
            client.connect(
                hostname=params.host,
                port=params.port,
                username=params.username,
                password=params.password,
                timeout=params.timeout,
                allow_agent=False,
                look_for_keys=False
            )

        # Store connection
        _ssh_connections[session_id] = client

        import json
        return json.dumps({
            "status": "connected",
            "session_id": session_id,
            "host": params.host,
            "port": params.port,
            "username": params.username,
            "message": f"Successfully connected to {params.host}:{params.port} as {params.username}"
        }, indent=2)

    except Exception as e:
        return _handle_ssh_error(e)


@mcp.tool(
    name="ssh_status",
    annotations={
        "title": "Check SSH Connection Status",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def ssh_status(params: StatusInput) -> str:
    """
    Check the status of SSH connection sessions.

    This tool reports which SSH sessions are active and their connection details.

    Args:
        params (StatusInput): Validated input parameters containing:
            - session_id (Optional[str]): Specific session to check, or None to list all active sessions

    Returns:
        str: JSON-formatted status information for active sessions

    Examples:
        - Use when: "Check all active SSH connections" -> params with session_id=None
        - Use when: "Verify if connection to server is still active" -> params with specific session_id
        - Don't use when: Need to execute commands (use ssh_execute instead)

    Error Handling:
        - Returns "No active sessions" if no connections are established
        - Returns specific session info if session_id is provided and valid
    """
    import json

    if params.session_id:
        # Check specific session
        if params.session_id in _ssh_connections:
            client = _ssh_connections[params.session_id]
            transport = client.get_transport() if client else None
            status = {
                "session_id": params.session_id,
                "active": True,
                "transport_active": transport.is_active() if transport else False
            }
            return json.dumps(status, indent=2)
        else:
            return json.dumps({
                "session_id": params.session_id,
                "active": False,
                "message": "Session not found"
            }, indent=2)
    else:
        # List all sessions
        active_sessions = []
        for sid, client in _ssh_connections.items():
            transport = client.get_transport() if client else None
            active_sessions.append({
                "session_id": sid,
                "active": True,
                "transport_active": transport.is_active() if transport else False
            })

        result = {
            "total_active_sessions": len(active_sessions),
            "sessions": active_sessions
        }
        return json.dumps(result, indent=2)


@mcp.tool(
    name="ssh_execute",
    annotations={
        "title": "Execute Remote Command",
        "readOnlyHint": True,
        "destructiveHint": True,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def ssh_execute(params: ExecuteInput) -> str:
    """
    Execute a command on the remote server via SSH.

    This tool runs a shell command on the connected server and captures stdout,
    stderr, and exit code. The command runs in a non-interactive shell.

    Args:
        params (ExecuteInput): Validated input parameters containing:
            - session_id (str): SSH session identifier from ssh_connect
            - command (str): Command to execute on remote server (e.g., "ls -la", "whoami", "cat /etc/os-release")
            - working_directory (Optional[str]): Working directory for command execution (e.g., "/var/log")
            - timeout (int): Execution timeout in seconds, default 30, range 1-600
            - response_format (ResponseFormat): Output format (markdown or json)

    Returns:
        str: Command execution result with stdout, stderr, and exit code

    Examples:
        - Use when: "Check what Linux distribution is running" -> params with command="cat /etc/os-release"
        - Use when: "List files in /var/log" -> params with command="ls -la /var/log"
        - Use when: "Check disk usage" -> params with command="df -h"
        - Don't use when: Need interactive commands (e.g., vim, top - use non-interactive alternatives)
        - Don't use when: Need to run multiple commands in sequence (execute tools separately)

    Error Handling:
        - Returns "Error: Session not found" if session_id is invalid
        - Returns execution result with non-zero exit code if command fails
        - Returns timeout error if command exceeds timeout limit
    """
    try:
        client = _ssh_connections.get(params.session_id)
        if not client:
            return "Error: Session not found. Use ssh_connect to establish a connection first."

        # Prepare command with working directory if specified
        full_command = params.command
        if params.working_directory:
            full_command = f"cd {params.working_directory} && {params.command}"

        # Execute command with stdin, stdout, stderr
        stdin, stdout, stderr = client.exec_command(full_command, timeout=params.timeout)

        # Wait for command to complete
        exit_code = stdout.channel.recv_exit_status()

        # Read output
        output = stdout.read().decode('utf-8')
        errors = stderr.read().decode('utf-8')

        result = _format_command_result(output, errors, exit_code)

        # Format response based on requested format
        if params.response_format == ResponseFormat.MARKDOWN:
            lines = ["## Command Execution Result"]
            lines.append(f"**Command**: `{full_command}`")
            lines.append(f"**Exit Code**: {exit_code}")
            lines.append("")

            if output:
                lines.append("### Standard Output")
                lines.append("```")
                lines.append(output)
                lines.append("```")
                lines.append("")

            if errors:
                lines.append("### Standard Error")
                lines.append("```")
                lines.append(errors)
                lines.append("```")
                lines.append("")

            lines.append(f"**Success**: {'Yes' if exit_code == 0 else 'No'}")

            return "\n".join(lines)
        else:
            import json
            return json.dumps(result, indent=2, ensure_ascii=False)

    except Exception as e:
        return _handle_ssh_error(e)


@mcp.tool(
    name="ssh_upload_file",
    annotations={
        "title": "Upload File to Remote Server",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": False,
        "openWorldHint": True
    }
)
async def ssh_upload_file(params: UploadFileInput) -> str:
    """
    Upload a local file to the remote server via SFTP.

    This tool transfers a file from the local machine to the connected SSH server.

    Args:
        params (UploadFileInput): Validated input parameters containing:
            - session_id (str): SSH session identifier from ssh_connect
            - local_path (str): Path to local file to upload (e.g., "./config.json", "/tmp/data.csv")
            - remote_path (str): Destination path on remote server (e.g., "/tmp/config.json", "~/mydata.csv")
            - file_mode (int): File permissions in octal, default 0o644 (rw-r--r--)

    Returns:
        str: Upload confirmation with file size and paths

    Examples:
        - Use when: "Upload config.json to /tmp/" -> params with local_path="./config.json", remote_path="/tmp/config.json"
        - Use when: "Transfer script to home directory" -> params with local_path="script.sh", remote_path="~/script.sh"
        - Don't use when: Remote file already exists (use ssh_execute with rm first or set file_mode accordingly)
        - Don't use when: Need to upload multiple files (call this tool multiple times)

    Error Handling:
        - Returns "Error: Session not found" if session_id is invalid
        - Returns error if local file doesn't exist
        - Returns error if remote directory doesn't have write permissions
        - Returns error if file size is too large for available bandwidth
    """
    try:
        client = _ssh_connections.get(params.session_id)
        if not client:
            return "Error: Session not found. Use ssh_connect to establish a connection first."

        # Open SFTP channel
        sftp = client.open_sftp()
        local_file = Path(params.local_path)

        # Upload file
        sftp.put(str(local_file), params.remote_path)

        # Set file permissions
        sftp.chmod(params.remote_path, params.file_mode)

        # Get remote file info
        remote_attrs = sftp.stat(params.remote_path)

        sftp.close()

        import json
        return json.dumps({
            "status": "success",
            "local_path": params.local_path,
            "remote_path": params.remote_path,
            "size": remote_attrs.st_size,
            "size_formatted": _format_size(remote_attrs.st_size),
            "permissions": oct(params.file_mode),
            "message": f"Successfully uploaded {_format_size(remote_attrs.st_size)} to {params.remote_path}"
        }, indent=2)

    except Exception as e:
        return _handle_ssh_error(e)


@mcp.tool(
    name="ssh_download_file",
    annotations={
        "title": "Download File from Remote Server",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ssh_download_file(params: DownloadFileInput) -> str:
    """
    Download a file from the remote server to the local machine via SFTP.

    This tool transfers a file from the connected SSH server to the local machine.

    Args:
        params (DownloadFileInput): Validated input parameters containing:
            - session_id (str): SSH session identifier from ssh_connect
            - remote_path (str): Path to remote file to download (e.g., "/var/log/syslog")
            - local_path (str): Destination path for downloaded file (e.g., "./syslog", "/tmp/downloaded.log")
            - overwrite (bool): Overwrite local file if it exists, default False

    Returns:
        str: Download confirmation with file size and paths

    Examples:
        - Use when: "Download /var/log/syslog to local machine" -> params with remote_path="/var/log/syslog", local_path="./syslog"
        - Use when: "Get config file from server" -> params with remote_path="/etc/app/config", local_path="config"
        - Don't use when: Local file exists and overwrite=False
        - Don't use when: Need to download multiple files (call this tool multiple times)

    Error Handling:
        - Returns "Error: Session not found" if session_id is invalid
        - Returns error if remote file doesn't exist
        - Returns error if local file exists and overwrite=False
        - Returns error if local directory doesn't have write permissions
    """
    try:
        client = _ssh_connections.get(params.session_id)
        if not client:
            return "Error: Session not found. Use ssh_connect to establish a connection first."

        # Check if local file exists
        local_file = Path(params.local_path)
        if local_file.exists() and not params.overwrite:
            return f"Error: Local file already exists at {params.local_path}. Set overwrite=True to replace it."

        # Open SFTP channel
        sftp = client.open_sftp()

        # Get remote file info before download
        remote_attrs = sftp.stat(params.remote_path)

        # Ensure parent directory exists
        local_file.parent.mkdir(parents=True, exist_ok=True)

        # Download file
        sftp.get(params.remote_path, str(local_file))
        sftp.close()

        import json
        return json.dumps({
            "status": "success",
            "remote_path": params.remote_path,
            "local_path": params.local_path,
            "size": remote_attrs.st_size,
            "size_formatted": _format_size(remote_attrs.st_size),
            "message": f"Successfully downloaded {_format_size(remote_attrs.st_size)} from {params.remote_path}"
        }, indent=2)

    except Exception as e:
        return _handle_ssh_error(e)


@mcp.tool(
    name="ssh_list_files",
    annotations={
        "title": "List Remote Directory",
        "readOnlyHint": True,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": True
    }
)
async def ssh_list_files(params: ListFilesInput) -> str:
    """
    List files and directories in a remote directory via SFTP.

    This tool provides a directory listing with file metadata including size,
    type, and modification time.

    Args:
        params (ListFilesInput): Validated input parameters containing:
            - session_id (str): SSH session identifier from ssh_connect
            - remote_path (str): Path to remote directory to list (e.g., "/var/log", "~", "/tmp")
            - show_hidden (bool): Show hidden files (starting with .), default False
            - response_format (ResponseFormat): Output format (markdown or json)

    Returns:
        str: Directory listing with file details

    Examples:
        - Use when: "List files in /var/log" -> params with remote_path="/var/log"
        - Use when: "Show all files including hidden ones in home directory" -> params with remote_path="~", show_hidden=True
        - Use when: "Check what's in /tmp" -> params with remote_path="/tmp"
        - Don't use when: Need to list files on local machine (use local filesystem instead)

    Error Handling:
        - Returns "Error: Session not found" if session_id is invalid
        - Returns error if remote directory doesn't exist
        - Returns error if directory is not readable due to permissions
    """
    try:
        client = _ssh_connections.get(params.session_id)
        if not client:
            return "Error: Session not found. Use ssh_connect to establish a connection first."

        # Open SFTP channel
        sftp = client.open_sftp()

        # List directory contents
        try:
            entries = sftp.listdir_attr(params.remote_path)
        except IOError as e:
            sftp.close()
            if "Permission denied" in str(e):
                return f"Error: Permission denied to read directory: {params.remote_path}"
            if "No such file" in str(e):
                return f"Error: Directory not found: {params.remote_path}"
            return f"Error: Could not list directory: {str(e)}"

        sftp.close()

        # Format entries
        files = []
        for entry in entries:
            if not params.show_hidden and entry.filename.startswith('.'):
                continue

            file_info = _format_file_attrs(entry)
            file_info['filename'] = entry.filename
            files.append(file_info)

        # Format response based on requested format
        if params.response_format == ResponseFormat.MARKDOWN:
            return _format_file_list_markdown(files, params.remote_path)
        else:
            import json
            return json.dumps({
                "path": params.remote_path,
                "total_items": len(files),
                "files": files
            }, indent=2, ensure_ascii=False)

    except Exception as e:
        return _handle_ssh_error(e)


@mcp.tool(
    name="ssh_disconnect",
    annotations={
        "title": "Disconnect SSH Session",
        "readOnlyHint": False,
        "destructiveHint": False,
        "idempotentHint": True,
        "openWorldHint": False
    }
)
async def ssh_disconnect(params: DisconnectInput) -> str:
    """
    Close an SSH connection session.

    This tool terminates an SSH session and frees associated resources.

    Args:
        params (DisconnectInput): Validated input parameters containing:
            - session_id (str): SSH session identifier to close

    Returns:
        str: Disconnection confirmation

    Examples:
        - Use when: "Close SSH connection to server" -> params with session_id="admin@192.168.1.100:22"
        - Use when: "Done working with server, disconnect" -> params with session_id (from ssh_connect)
        - Don't use when: Session doesn't exist (ssh_status will show this)
        - Don't use when: Need to continue working with the server

    Error Handling:
        - Returns "Error: Session not found" if session_id is invalid
        - Returns success even if session was already closed
    """
    try:
        session_id = params.session_id

        if session_id not in _ssh_connections:
            import json
            return json.dumps({
                "status": "not_found",
                "session_id": session_id,
                "message": "Session not found or already closed"
            }, indent=2)

        client = _ssh_connections.pop(session_id)

        if client:
            client.close()

        import json
        return json.dumps({
            "status": "disconnected",
            "session_id": session_id,
            "message": f"Successfully disconnected session: {session_id}"
        }, indent=2)

    except Exception as e:
        return _handle_ssh_error(e)


def main() -> None:
    """Entry point for the SSH MCP server."""
    mcp.run()
