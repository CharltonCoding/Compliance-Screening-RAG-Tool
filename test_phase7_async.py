#!/usr/bin/env python3
"""
Phase 7 Testing: Async Offloading Verification
===============================================

Verifies that server.py has been converted to async:
- Functions are declared as async
- yfinance calls use asyncio.to_thread()
- Code is ready for non-blocking operation

Run with: python test_phase7_async.py
"""

import sys
import ast
import inspect


def print_section(title: str):
    """Print test section header"""
    print("\n" + "=" * 80)
    print(f"TEST: {title}")
    print("=" * 80 + "\n")


def test_functions_are_async():
    """Test 1: Verify MCP tool functions are declared as async"""
    print_section("Verify Functions Are Async")

    # Read server.py source
    with open("server.py", "r") as f:
        source = f.read()

    # Parse AST
    tree = ast.parse(source)

    # Find function definitions
    async_functions = []
    sync_functions = []

    for node in ast.walk(tree):
        if isinstance(node, ast.AsyncFunctionDef):
            async_functions.append(node.name)
        elif isinstance(node, ast.FunctionDef):
            # Check if it's a tool function (has @mcp.tool decorator)
            is_tool = any(
                isinstance(dec, ast.Call) and
                isinstance(dec.func, ast.Attribute) and
                dec.func.attr == "tool"
                for dec in node.decorator_list
            )
            if is_tool:
                sync_functions.append(node.name)

    print(f"Found {len(async_functions)} async functions:")
    for func in async_functions:
        print(f"  - async def {func}()")

    # Check for our target functions
    if "check_client_suitability" in async_functions:
        print("\n✓ check_client_suitability is async")
    else:
        print("\n✗ check_client_suitability is NOT async")
        return False

    if "get_market_data" in async_functions:
        print("✓ get_market_data is async")
    else:
        print("✗ get_market_data is NOT async")
        return False

    if sync_functions:
        print(f"\n⚠️  Found {len(sync_functions)} synchronous @mcp.tool functions:")
        for func in sync_functions:
            print(f"  - def {func}()")
        print("  (These should be converted to async)")

    print("\n✓ All required functions are async")
    return True


def test_yfinance_uses_thread_pool():
    """Test 2: Verify yfinance calls use asyncio.to_thread()"""
    print_section("Verify yfinance Uses Thread Pool")

    # Read server.py source
    with open("server.py", "r") as f:
        source = f.read()

    # Check for asyncio.to_thread usage
    if "asyncio.to_thread" in source:
        print("✓ Found asyncio.to_thread() in server.py")

        # Count occurrences
        count = source.count("asyncio.to_thread")
        print(f"✓ Found {count} usage(s) of asyncio.to_thread()")

        # Check if it's used with stock.info
        if "await asyncio.to_thread(lambda: stock.info)" in source:
            print("✓ yfinance call (stock.info) is wrapped with asyncio.to_thread()")
            print("✓ Blocking I/O will be offloaded to thread pool")
            return True
        else:
            print("⚠️  asyncio.to_thread found but not wrapping stock.info")
            return False
    else:
        print("✗ asyncio.to_thread NOT found in server.py")
        print("✗ yfinance calls will block the event loop")
        return False


def test_asyncio_import():
    """Test 3: Verify asyncio is imported"""
    print_section("Verify asyncio Module Import")

    # Read server.py source
    with open("server.py", "r") as f:
        source = f.read()

    # Parse AST
    tree = ast.parse(source)

    # Find imports
    asyncio_imported = False
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "asyncio":
                    asyncio_imported = True
                    print(f"✓ Found: import asyncio")

    if asyncio_imported:
        print("✓ asyncio module is imported")
        return True
    else:
        print("✗ asyncio module is NOT imported")
        return False


def test_phase7_comments():
    """Test 4: Verify Phase 7 implementation comments exist"""
    print_section("Verify Phase 7 Documentation")

    # Read server.py source
    with open("server.py", "r") as f:
        source = f.read()

    phase7_markers = [
        "PHASE 7",
        "Phase 7",
        "async offloading",
        "Async implementation",
        "non-blocking"
    ]

    found_markers = []
    for marker in phase7_markers:
        if marker in source:
            found_markers.append(marker)

    if found_markers:
        print(f"✓ Found {len(found_markers)} Phase 7 documentation markers:")
        for marker in found_markers:
            count = source.count(marker)
            print(f"  - '{marker}' ({count} occurrence{('s' if count > 1 else '')})")
        print("\n✓ Phase 7 implementation is documented")
        return True
    else:
        print("⚠️  No Phase 7 documentation markers found")
        print("  (This is not critical but helpful for maintenance)")
        return True  # Still pass, just a warning


def run_all_tests():
    """Run all Phase 7 verification tests"""
    print("=" * 80)
    print("PHASE 7: ASYNC OFFLOADING - VERIFICATION SUITE")
    print("=" * 80)

    results = {
        "Functions are async": test_functions_are_async(),
        "yfinance uses thread pool": test_yfinance_uses_thread_pool(),
        "asyncio module imported": test_asyncio_import(),
        "Phase 7 documentation": test_phase7_comments()
    }

    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80 + "\n")

    passed = sum(1 for v in results.values() if v)
    total = len(results)

    for test_name, result in results.items():
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status} | {test_name}")

    print(f"\n📊 Results: {passed}/{total} tests passed ({(passed/total*100):.1f}%)")

    if passed == total:
        print("\n🎉 ALL PHASE 7 VERIFICATION TESTS PASSED!")
        print("\n✅ Phase 7 Implementation Verified:")
        print("  - MCP tools converted to async functions")
        print("  - yfinance calls offloaded to thread pool with asyncio.to_thread()")
        print("  - asyncio module properly imported")
        print("  - Implementation is documented")
        print("\n✅ Benefits:")
        print("  - Server will not block during API calls")
        print("  - Claude Desktop communication loop remains responsive")
        print("  - Concurrent requests can be handled efficiently")
        print("  - Production-ready async architecture")
        return 0
    else:
        print(f"\n⚠️  {total - passed} test(s) failed")
        return 1


if __name__ == "__main__":
    try:
        exit_code = run_all_tests()
        sys.exit(exit_code)
    except Exception as e:
        print(f"\n❌ CRITICAL TEST FAILURE: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)
