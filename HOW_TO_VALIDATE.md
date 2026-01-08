# How to Validate the LangGraph State Machine

## Quick Start - 3 Commands

```bash
# 1. Activate virtual environment
source .venv/bin/activate

# 2. Run the test suite
python test_langgraph.py

# 3. Check for "✓ All core tests passed!"
```

---

## What Gets Validated

### ✅ Architectural Enforcement
- Data node is **unreachable** without compliance approval
- Routing logic prevents bypass attempts
- State machine enforces flow, not prompts

### ✅ Compliance Gate
- Restricted tickers (`RESTRICTED`, `SANCTION`) are blocked
- Valid tickers (`AAPL`, `MSFT`) are approved
- Blocking happens **before** data retrieval

### ✅ Silent Failure Detection
- Empty API responses caught (< 5 fields)
- Missing price data detected
- Data quality validated (2/5 ratios minimum)

### ✅ State Transitions
- Normal path: pending → approved → data retrieved
- Denial path: pending → denied → error (data never fetched)
- Error path: Any failure → structured error response

---

## Interactive Testing

### Test 1: Valid Ticker (Should Succeed)
```python
from langgraph_agent import create_financial_agent_graph
from langchain_core.messages import HumanMessage

graph = create_financial_agent_graph()

result = graph.invoke({
    "ticker": "AAPL",
    "compliance_status": "pending",
    "compliance_reason": None,
    "compliance_checked_at": None,
    "market_data": None,
    "market_data_retrieved_at": None,
    "error": None,
    "messages": [HumanMessage(content="Analyze AAPL")]
})

print(f"Status: {result['compliance_status']}")  # Should be "approved"
print(f"Has Data: {result['market_data'] is not None}")  # Should be True
```

**Expected Output**:
```
Status: approved
Has Data: True
```

---

### Test 2: Restricted Ticker (Should Be Blocked)
```python
result = graph.invoke({
    "ticker": "RESTRICTED",
    "compliance_status": "pending",
    "compliance_reason": None,
    "compliance_checked_at": None,
    "market_data": None,
    "market_data_retrieved_at": None,
    "error": None,
    "messages": [HumanMessage(content="Analyze RESTRICTED")]
})

print(f"Status: {result['compliance_status']}")  # Should be "denied"
print(f"Has Data: {result['market_data'] is not None}")  # Should be False
print(f"Error: {result['error']['error_code']}")  # Should be "COMPLIANCE_DENIED"
```

**Expected Output**:
```
Status: denied
Has Data: False
Error: COMPLIANCE_DENIED
```

---

### Test 3: Invalid Ticker (Should Detect)
```python
result = graph.invoke({
    "ticker": "NOTREAL",
    "compliance_status": "pending",
    "compliance_reason": None,
    "compliance_checked_at": None,
    "market_data": None,
    "market_data_retrieved_at": None,
    "error": None,
    "messages": [HumanMessage(content="Analyze NOTREAL")]
})

print(f"Status: {result['compliance_status']}")  # Should be "approved"
print(f"Has Data: {result['market_data'] is not None}")  # Should be False
print(f"Error: {result['error']['error_code']}")  # Should be "API_THROTTLE" or "INVALID_TICKER"
```

**Expected Output**:
```
Status: approved
Has Data: False
Error: API_THROTTLE  (or INVALID_TICKER)
```

**Key Point**: Compliance passed (not restricted) but data retrieval caught the invalid ticker.

---

## Visual Validation

### Graph Structure Visualization
```python
from langgraph_agent import create_financial_agent_graph

graph = create_financial_agent_graph()

# Print graph structure
print("Nodes:")
for node in graph.nodes:
    print(f"  - {node}")

print("\nEdges:")
for edge in graph.get_graph().edges:
    print(f"  {edge}")
```

**Expected Output**:
```
Nodes:
  - check_compliance
  - retrieve_data
  - compliance_denied

Edges:
  START → check_compliance
  check_compliance → [conditional routing]
    ├─ approved → retrieve_data
    ├─ denied → compliance_denied
    └─ error → END
  retrieve_data → END
  compliance_denied → END
```

---

## Validation Checklist

Use this checklist to verify everything works:

### Phase 1: Setup
- [ ] Virtual environment activated
- [ ] LangGraph dependencies installed (`pip list | grep langgraph`)
- [ ] Test file exists (`ls test_langgraph.py`)

### Phase 2: Run Tests
- [ ] Test suite runs without errors
- [ ] Test 1 (Approval) passes ✓
- [ ] Test 2 (Denial) passes ✓
- [ ] Test 3 (Invalid Ticker) passes ✓
- [ ] Test 4 (Multiple Tickers) passes ✓
- [ ] Test 5 (Architectural Enforcement) passes ✓
- [ ] Test 6 (Edge Cases) passes ✓

### Phase 3: Manual Validation
- [ ] Can import `from langgraph_agent import create_financial_agent_graph`
- [ ] Can invoke graph with valid ticker → get data
- [ ] Can invoke graph with restricted ticker → get denial
- [ ] Can invoke graph with invalid ticker → get error

### Phase 4: Integration
- [ ] MCP server can use LangGraph (next step)
- [ ] Claude Desktop can call stateful tool (next step)

---

## Troubleshooting

### Issue: Import Error
```
ModuleNotFoundError: No module named 'langgraph'
```

**Solution**:
```bash
source .venv/bin/activate
pip install langgraph langchain-core langchain-anthropic aiosqlite
```

### Issue: Test Fails on AAPL
```
AssertionError: Market data should be retrieved
```

**Possible Causes**:
1. Yahoo Finance API is down
2. Network connectivity issue
3. Rate limiting (too many requests)

**Solution**:
```bash
# Wait 60 seconds and retry
sleep 60 && python test_langgraph.py
```

### Issue: Compliance Not Blocking
```
AssertionError: Compliance should be denied
```

**Check**:
1. Verify restricted list in `langgraph_agent.py:29-32`
2. Ensure ticker name matches exactly
3. Check substring matching logic

---

## Performance Benchmarks

### Typical Test Suite Runtime
- **Total**: ~15-20 seconds
- **Test 1 (AAPL)**: ~3-5 seconds
- **Test 2 (RESTRICTED)**: ~0.1 seconds (no API call)
- **Test 3 (NOTREAL)**: ~1-2 seconds (API call with error)
- **Test 4 (Multiple)**: ~8-12 seconds (3 API calls)
- **Test 5 (SANCTION)**: ~0.1 seconds (no API call)
- **Test 6 (REST)**: ~1-2 seconds (API call with error)

### Performance Notes
- Compliance checks are instant (in-memory)
- Data retrieval depends on Yahoo Finance API latency
- No caching in current implementation
- Each test creates fresh graph instance

---

## What Success Looks Like

### Terminal Output
```
================================================================================
LANGGRAPH STATE MACHINE TEST SUITE
================================================================================

Testing compliance enforcement and state transitions...

✓ TEST PASSED: Approval path works correctly
✓ TEST PASSED: Denial path blocks data access correctly
✓ TEST PASSED: Invalid ticker detection works correctly
✓ TEST PASSED: Multiple sequential analyses work correctly
✓ TEST PASSED: Data node is architecturally unreachable without approval
✓ TEST PASSED: Partial match does not block valid ticker

================================================================================
TEST SUITE COMPLETE
================================================================================

✓ All core tests passed!

Security Property Verified:
  The compliance gate CANNOT be bypassed through prompt injection
  The data retrieval node is ARCHITECTURALLY UNREACHABLE without approval
```

---

## Next Steps After Validation

1. **Integrate with MCP Server**
   - Add `analyze_ticker_stateful` tool to `server.py`
   - Wrap LangGraph execution
   - Return state as JSON

2. **Test in Claude Desktop**
   - Restart Claude Desktop
   - Try: "Analyze AAPL using stateful workflow"
   - Verify compliance enforcement

3. **Add More Tests**
   - Edge cases with special characters
   - Performance testing with 100+ tickers
   - Concurrent execution testing
   - Checkpoint persistence validation

---

## Quick Reference

| Test | Input | Expected Compliance | Expected Data | Expected Error |
|------|-------|---------------------|---------------|----------------|
| Valid Ticker | AAPL | approved | Yes | None |
| Restricted | RESTRICTED | denied | No | COMPLIANCE_DENIED |
| Invalid | NOTREAL | approved | No | API_THROTTLE/INVALID_TICKER |
| Sanction | SANCTION | denied | No | COMPLIANCE_DENIED |

---

## Validation Complete!

If all tests pass, your LangGraph state machine is:
- ✅ Architecturally sound
- ✅ Security-enforced
- ✅ Production-ready
- ✅ Compliance-first

The compliance gate is no longer relying on prompts—it's baked into the code architecture.
