# Quick Setup Guide for Company A Financial Intelligence Node

## Prerequisites Checklist
- [ ] Python 3.9+ installed (`python --version`)
- [ ] Claude Desktop app installed and running
- [ ] Terminal/command line access

---

## Step-by-Step Installation

### 1. Install Dependencies

From the project directory, run:

```bash
# Using uv (recommended - faster)
uv pip install -e .

# OR using pip
pip install -e .
```

This installs:
- `fastmcp` - Model Context Protocol framework
- `yfinance` - Yahoo Finance API for market data

---

### 2. Find Your Claude Desktop Config File

**macOS:**
```bash
open ~/Library/Application\ Support/Claude/
```
Look for `claude_desktop_config.json`

**Windows:**
```
%APPDATA%\Claude\claude_desktop_config.json
```

**Linux:**
```
~/.config/Claude/claude_desktop_config.json
```

---

### 3. Configure Claude Desktop

Open `claude_desktop_config.json` in a text editor.

If the file doesn't exist, create it with this content:

```json
{
  "mcpServers": {
    "financial-intel": {
      "command": "uv",
      "args": [
        "--directory",
        "/Users/adamcharlrton/companya-integration-node",
        "run",
        "python",
        "server.py"
      ]
    }
  }
}
```

**IMPORTANT**: Replace `/Users/adamcharlrton/companya-integration-node` with your actual project path.

To get your full project path:
```bash
# Run this in your project directory
pwd
```

#### Alternative: Using Python directly (if not using uv)

If you prefer not to use `uv`, change the config to:

```json
{
  "mcpServers": {
    "financial-intel": {
      "command": "python",
      "args": [
        "/Users/adamcharlrton/companya-integration-node/server.py"
      ]
    }
  }
}
```

---

### 4. Restart Claude Desktop

**CRITICAL**: You must completely quit and restart Claude Desktop:

**macOS:**
- `Cmd + Q` to quit (or right-click dock icon → Quit)
- Reopen from Applications

**Windows:**
- Right-click system tray → Exit
- Reopen from Start menu

---

### 5. Verify Installation

After restarting Claude Desktop, you should see the MCP server tools available.

Open a new chat and try:

```
You: "What tools do you have access to?"
```

Claude should mention:
- `check_client_suitability`
- `get_market_data`

---

## Test the Integration

### Test 1: Compliance Check
```
You: "Check if JPMorgan (JPM) is available for analysis"
```

Expected: Claude uses `check_client_suitability` and returns APPROVED status.

### Test 2: Market Data Retrieval
```
You: "Get market data for Apple (AAPL)"
```

Expected: Claude first checks compliance, then fetches structured market data.

### Test 3: Restricted Entity
```
You: "Analyze RESTRICTED ticker"
```

Expected: Claude checks compliance and receives DENIED status, refuses to proceed.

---

## Troubleshooting

### Issue: Tools don't appear in Claude Desktop

**Solution 1**: Check config file syntax
- Ensure valid JSON (no trailing commas)
- Use a JSON validator: https://jsonlint.com

**Solution 2**: Verify project path
```bash
# Make sure this path exists
ls /Users/adamcharlrton/companya-integration-node/server.py
```

**Solution 3**: Check logs
```bash
# macOS
tail -f ~/Library/Logs/Claude/mcp*.log

# Look for error messages about the server
```

### Issue: Import errors or module not found

```bash
# Reinstall dependencies
uv pip install --force-reinstall -e .

# Verify fastmcp is installed
python -c "import fastmcp; print(fastmcp.__version__)"
```

### Issue: Server crashes immediately

Check if Python version is correct:
```bash
python --version  # Should be 3.9 or higher
```

Run the server directly to see errors:
```bash
python server.py
# Should hang waiting for MCP commands (this is correct)
# Press Ctrl+C to stop
```

---

## Advanced Configuration

### Running Multiple MCP Servers

You can add multiple servers to your config:

```json
{
  "mcpServers": {
    "financial-intel": {
      "command": "uv",
      "args": ["--directory", "/path/to/companya-integration-node", "run", "python", "server.py"]
    },
    "another-server": {
      "command": "uv",
      "args": ["--directory", "/path/to/another-mcp", "run", "python", "server.py"]
    }
  }
}
```

### Using a Virtual Environment

If you want to use a specific virtual environment:

```json
{
  "mcpServers": {
    "financial-intel": {
      "command": "/Users/adamcharlrton/companya-integration-node/.venv/bin/python",
      "args": [
        "/Users/adamcharlrton/companya-integration-node/server.py"
      ]
    }
  }
}
```

---

## Next Steps

Once setup is complete:

1. Customize the restricted entities list in [server.py:29-32](server.py#L29-L32)
2. Add additional market data fields as needed
3. Extend with new tools (e.g., `generate_investment_memo`)
4. Connect to real internal data sources

---

## Resources

- MCP Documentation: https://modelcontextprotocol.io
- FastMCP GitHub: https://github.com/jlowin/fastmcp
- Claude API Docs: https://docs.anthropic.com

---

## Getting Help

If you're still stuck:

1. Check Claude Desktop logs for specific errors
2. Verify all installation steps were completed
3. Try running the server manually: `python server.py`
4. Check that dependencies installed correctly: `pip list | grep fastmcp`
