# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Common Commands

### Installation
```bash
pip install ssh-mcp
```

Or install from source:
```bash
pip install -e .
```

### Running the server
```bash
ssh-mcp
# or
python -m ssh_mcp
```

### Testing with MCP Inspector
```bash
npx @modelcontextprotocol/inspector python -m ssh_mcp
```

### Code style
```bash
black ssh_mcp/  # Format code
mypy ssh_mcp/   # Type checking
```

## Architecture

This is a single-file MCP server that provides SSH functionality (command execution, file transfer, directory listing) via the FastMCP framework.

### Core Patterns

**FastMCP Tool Registration**: All SSH operations are exposed as MCP tools using `@mcp.tool()` decorator. Each tool:
- Defines a Pydantic input model for validation
- Returns string-formatted responses (JSON or markdown)
- Uses async functions (though paramiko calls are blocking)

**Session Management**: SSH connections are stored in a module-level dictionary `_ssh_connections` keyed by `session_id`. Sessions persist as long as the server runs.

**Input Validation**: Each tool has a dedicated Pydantic model (e.g., `ConnectInput`, `ExecuteInput`) with:
- Field validators (e.g., `_validate_command` prevents injection)
- Config with `extra='forbid'` to reject unknown parameters
- Type annotations for all fields

**Response Formatting**: Two output formats are supported:
- `markdown` - human-readable with formatting
- `json` - machine-readable structured data

**Error Handling**: `_handle_ssh_error()` normalizes paramiko exceptions into user-friendly messages covering auth failures, connection issues, timeouts, etc.

### Tool Dependencies

All tools except `ssh_connect` require a valid `session_id` from an established connection. The workflow is:
1. `ssh_connect` → establishes connection, returns `session_id`
2. Other tools → use `session_id` to operate on that connection
3. `ssh_disconnect` → closes the session

### Adding New Tools

When adding a new SSH operation:
1. Create a Pydantic input model with `ConnectInput`-style validation
2. Use `@mcp.tool()` decorator with appropriate annotations
3. Call `_ssh_connections.get(session_id)` to retrieve the SSHClient
4. Handle errors with `try/except` and `_handle_ssh_error()`
5. Return responses formatted as JSON or markdown

### Authentication

Supports two auth methods in `ssh_connect`:
- Password: provide `password` parameter
- SSH key: provide `private_key_path` (optionally `private_key_password` for encrypted keys)

Host key verification uses `AutoAddPolicy` - appropriate for development but should be reviewed for production use.
