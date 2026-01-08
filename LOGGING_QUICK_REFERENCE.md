# Structured Logging - Quick Reference Card

## 🚀 Quick Start

```bash
# Run demonstration
python test_logging_standalone.py

# Analyze logs
python analyze_logs.py

# View logs
cat logs/mcp-server.log | python -m json.tool | less
cat logs/security-audit.log | python -m json.tool | less
```

---

## 📊 RFC 5424 Severity Levels

| Level | Name          | Usage                                    |
|-------|---------------|------------------------------------------|
| 0     | EMERGENCY     | System unusable                          |
| 1     | ALERT         | Immediate action required                |
| 2     | CRITICAL      | Critical conditions                      |
| 3     | ERROR         | Data retrieval errors                    |
| 4     | WARNING       | Compliance DENIED, silent failures       |
| 5     | NOTICE        | Compliance APPROVED (significant events) |
| 6     | INFORMATIONAL | Tool invocations, successes              |
| 7     | DEBUG         | Debug messages                           |

---

## 🔍 Common Log Queries

### Find all DENIED compliance attempts
```bash
cat logs/security-audit.log | jq -r '.ticker'
```

### Count operations by tool
```bash
cat logs/mcp-server.log | jq -r '.tool_name' | sort | uniq -c
```

### Find all operations in a session
```bash
CORRELATION_ID="18e2ace3-1c92-40eb-b11f-5c198c05f108"
cat logs/mcp-server.log | jq --arg id "$CORRELATION_ID" 'select(.correlation_id == $id)'
```

### Show all severity 3+ events (ERROR and above)
```bash
cat logs/mcp-server.log | jq 'select(.severity <= 3)'
```

### Count silent failures by type
```bash
cat logs/mcp-server.log | \
  jq -r 'select(.event_type == "silent_failure_detection") | .failure_type' | \
  sort | uniq -c
```

---

## 📁 Log Files

| File                       | Purpose                              | When Written                         |
|----------------------------|--------------------------------------|--------------------------------------|
| `logs/mcp-server.log`      | All application logs                 | Every operation                      |
| `logs/security-audit.log`  | DENIED compliance attempts only      | Only when compliance check is DENIED |

---

## 🔑 Key Log Fields

| Field               | Type    | Description                                    |
|---------------------|---------|------------------------------------------------|
| `timestamp`         | string  | ISO 8601 UTC timestamp                         |
| `severity`          | int     | RFC 5424 level (0-7)                           |
| `correlation_id`    | string  | UUID for session tracking                      |
| `compliance_flag`   | string  | APPROVED, DENIED, PENDING, or N/A              |
| `tool_name`         | string  | MCP tool being invoked                         |
| `event_type`        | string  | Event classification                           |
| `ticker`            | string  | Entity being analyzed                          |
| `security_alert`    | bool    | True for DENIED compliance attempts            |

---

## 📋 Event Types

| Event Type                | Description                                    |
|---------------------------|------------------------------------------------|
| `tool_invocation`         | MCP tool called                                |
| `compliance_check`        | Compliance decision made                       |
| `tool_success`            | Tool completed successfully                    |
| `data_retrieval_error`    | Error retrieving market data                   |
| `silent_failure_detection`| API throttle or data quality issue detected    |

---

## 🚨 Security Alerts

### What triggers a security alert?

1. Compliance check returns DENIED
2. Ticker is on restricted list (RESTRICTED, SANCTION)
3. Event logged to both mcp-server.log AND security-audit.log

### Example security alert query
```bash
cat logs/mcp-server.log | jq 'select(.security_alert == true)'
```

---

## 💡 Common Use Cases

### Use Case 1: Investigate denied access
```bash
# Find all denied tickers
cat logs/security-audit.log | jq -r '[.timestamp, .ticker, .reason] | @tsv'
```

### Use Case 2: Track session operations
```bash
# Get correlation ID from latest log
CORR_ID=$(tail -1 logs/mcp-server.log | jq -r '.correlation_id')

# Show all operations in that session
cat logs/mcp-server.log | jq --arg id "$CORR_ID" 'select(.correlation_id == $id) | {timestamp, tool_name, message}'
```

### Use Case 3: Monitor error rate
```bash
# Count errors
ERROR_COUNT=$(cat logs/mcp-server.log | jq 'select(.severity == 3)' | wc -l)
TOTAL_COUNT=$(cat logs/mcp-server.log | wc -l)
echo "Error rate: $ERROR_COUNT / $TOTAL_COUNT"
```

### Use Case 4: Check silent failure detection
```bash
cat logs/mcp-server.log | \
  jq -r 'select(.event_type == "silent_failure_detection") |
         [.timestamp, .ticker, .failure_type, .detail] | @tsv' | \
  column -t -s $'\t'
```

---

## 🔧 Troubleshooting

### No logs appearing?
```bash
# Check if log directory exists
ls -la logs/

# Check logger initialization
python -c "from logging_config import structured_logger; print('Logger OK')"

# Check file permissions
ls -l logs/*.log
```

### Logs not in JSON format?
```bash
# Validate JSON
cat logs/mcp-server.log | jq . > /dev/null && echo "Valid JSON" || echo "Invalid JSON"
```

### Can't find correlation ID?
```bash
# Check server startup - correlation ID is printed at startup
python server.py 2>&1 | grep "Correlation ID"
```

---

## 📈 Performance Tips

1. **Use jq for parsing**: Much faster than Python for simple queries
2. **Tail for live monitoring**: `tail -f logs/mcp-server.log | jq .`
3. **Rotate logs daily**: Prevent files from growing too large
4. **Archive to S3/GCS**: Long-term storage with compression

---

## 🎯 CISO Checklist

- [ ] Verify security-audit.log contains DENIED attempts
- [ ] Confirm correlation IDs present in all logs
- [ ] Check RFC 5424 severity levels are correct
- [ ] Validate JSON format with jq
- [ ] Test log forwarding to SIEM
- [ ] Set up alerting for multiple DENIED attempts
- [ ] Document log retention policy
- [ ] Schedule regular compliance reviews

---

## 📚 Additional Resources

- Full documentation: [PHASE3_STRUCTURED_LOGGING.md](PHASE3_STRUCTURED_LOGGING.md)
- Test suite: [test_logging_standalone.py](test_logging_standalone.py)
- Log analysis: [analyze_logs.py](analyze_logs.py)
- Logger config: [logging_config.py](logging_config.py)

---

**Quick Help**: Run `python analyze_logs.py` for detailed report
