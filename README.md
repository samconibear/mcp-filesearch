# file-search-mcp

A cross-platform MCP server that lets Claude search your files by name, content, extension, or modification time.

Built with [FastMCP](https://github.com/jlowin/fastmcp), a Python framework for building MCP servers.

## Setup


Clone the repo anywhere you like
```bash
git clone https://github.com/samconibear/mcp-filesearch.git
```

Then run the setup script for your platform. It will create a virtual environment, install dependencies, and wire up `claude_desktop_config.json` automatically.

**macOS / Linux**
```bash
bash scripts/setup-unix.sh
```

**Windows** (PowerShell)
```powershell
.\scripts\setup-windows.ps1
```

Then restart Claude Desktop.

## Requirements

- Python 3.10 or newer
- Claude Desktop

## Search scope

All searches are scoped to a single **root directory** — the server cannot read files outside it. The root is set by the first argument passed to `main.py`.

The setup script defaults to your home directory (`~/`). To change it, edit the `args` field in `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "file-search": {
      "command": "/path/to/mcp-filesearch/.venv/bin/python",
      "args": [
        "/path/to/mcp-filesearch/src/main.py",
        "/the/directory/you/want/searched"
      ]
    }
  }
}
```

Then restart Claude Desktop. You can point it at any directory — your home folder, a specific project, a mounted drive, etc.

