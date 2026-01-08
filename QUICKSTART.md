# Quick Start - 3 Steps to Get Running

## Step 1: Install Dependencies
```bash
source .venv/bin/activate
pip install fastmcp yfinance
```

## Step 2: Configure Claude Desktop

Edit your Claude Desktop config file:
```bash
open ~/Library/Application\ Support/Claude/claude_desktop_config.json
```

Add this configuration (replace the path with your actual project path):
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

## Step 3: Restart Claude Desktop

**IMPORTANT**: Completely quit (Cmd+Q) and restart Claude Desktop.

---

## Test It Works

Open a new chat in Claude Desktop and try:

**Test 1: Check Tools**
```
What financial analysis tools do you have?
```

**Test 2: Analyze a Stock**
```
Get me the market data for Apple (AAPL)
```

**Test 3: Test Compliance**
```
Check if RESTRICTED ticker is available for analysis
```

---

## Project Structure

```
companya-integration-node/
├── server.py              # Main MCP server (run this)
├── README.md              # Full project documentation
├── SETUP_GUIDE.md         # Detailed setup instructions
├── QUICKSTART.md          # This file
├── pyproject.toml         # Python dependencies
└── .venv/                 # Virtual environment (Python 3.10)
```

---

## What This Project Does

1. **Compliance-First AI**: Every data request must pass a compliance check first
2. **Structured Data**: Returns JSON instead of text to prevent hallucinations
3. **Real-time Market Data**: Fetches live financial data via Yahoo Finance
4. **Enterprise Pattern**: Demonstrates how to activate AI for financial institutions

---

## Next Steps

- Customize restricted entities in [server.py:29-32](server.py#L29-L32)
- Add more market data fields
- Connect to real internal data sources
- Extend with additional tools (e.g., `generate_investment_memo`)

---

## Troubleshooting

**Tools don't appear?**
- Verify config path is correct
- Check Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log`
- Make sure you completely quit and restarted Claude Desktop

**Import errors?**
```bash
source .venv/bin/activate
pip install --force-reinstall fastmcp yfinance
```

**Need more help?**
See [SETUP_GUIDE.md](SETUP_GUIDE.md) for detailed troubleshooting.
