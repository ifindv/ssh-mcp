"""
SSH MCP Server

An MCP (Model Context Protocol) server that enables LLMs to interact with
remote servers via SSH, including command execution, file transfer, and directory listing.
"""

from ssh_mcp.server import main

__version__ = "1.0.0"
__all__ = ["main"]
