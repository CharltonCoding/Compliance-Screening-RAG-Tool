import { NextRequest, NextResponse } from 'next/server';

/**
 * API Route: /api/mcp/check-suitability
 *
 * Proxies requests to the Python MCP server's check_client_suitability tool.
 * This route acts as a bridge between the Next.js frontend and the Python backend.
 */
export async function POST(request: NextRequest) {
  try {
    const body = await request.json();
    const { ticker } = body;

    if (!ticker) {
      return NextResponse.json(
        { error: true, error_code: 'INVALID_INPUT', message: 'Ticker is required' },
        { status: 400 }
      );
    }

    // Call the Python MCP server
    // Note: Adjust the URL to match your MCP server's actual endpoint
    const mcpServerUrl = process.env.MCP_SERVER_URL || 'http://localhost:8000';

    const response = await fetch(`${mcpServerUrl}/tools/check_client_suitability`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({ ticker: ticker.toUpperCase() }),
    });

    if (!response.ok) {
      return NextResponse.json(
        {
          error: true,
          error_code: 'MCP_SERVER_ERROR',
          message: `MCP server returned ${response.status}`,
        },
        { status: response.status }
      );
    }

    const data = await response.json();
    return NextResponse.json(data);
  } catch (error) {
    console.error('Error calling MCP check_client_suitability:', error);
    return NextResponse.json(
      {
        error: true,
        error_code: 'INTERNAL_ERROR',
        message: error instanceof Error ? error.message : 'Unknown error',
      },
      { status: 500 }
    );
  }
}
