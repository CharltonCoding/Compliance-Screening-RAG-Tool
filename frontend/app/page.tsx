'use client';

import { useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import type { MarketDataResponse, ComplianceResponse } from '@/lib/mcp-client';

export default function Dashboard() {
  const [ticker, setTicker] = useState('');
  const [loading, setLoading] = useState(false);
  const [complianceData, setComplianceData] = useState<ComplianceResponse | null>(null);
  const [marketData, setMarketData] = useState<MarketDataResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [showComplianceDetails, setShowComplianceDetails] = useState(false);

  const handleQuery = async () => {
    if (!ticker) return;

    setLoading(true);
    setError(null);
    setComplianceData(null);
    setMarketData(null);

    try {
      // Step 1: Check compliance
      const complianceRes = await fetch('/api/mcp/check-suitability', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ticker: ticker.toUpperCase() }),
      });

      const compliance: ComplianceResponse = await complianceRes.json();
      setComplianceData(compliance);

      // Step 2: If approved, get market data
      if (compliance.compliance_status === 'APPROVED' && !compliance.error) {
        const marketRes = await fetch('/api/mcp/market-data', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ ticker: ticker.toUpperCase() }),
        });

        const market: MarketDataResponse = await marketRes.json();
        setMarketData(market);

        if (market.error) {
          setError(market.error_code || 'Failed to retrieve market data');
        }
      } else if (compliance.error) {
        setError(compliance.error_code || 'Compliance check failed');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-blue-50 to-slate-100">
      {/* Header */}
      <header className="bg-white/80 backdrop-blur-md border-b border-slate-200 shadow-sm sticky top-0 z-50">
        <div className="max-w-7xl mx-auto px-4 py-5">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 to-indigo-600 bg-clip-text text-transparent">
                Financial Intelligence MCP
              </h1>
              <p className="text-sm text-slate-600 mt-1">
                Enterprise-Grade Market Data with Multi-Layer Compliance Enforcement
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant="default" className="text-xs font-medium bg-gradient-to-r from-green-600 to-emerald-600 shadow-sm">
                Live System
              </Badge>
            </div>
          </div>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-8">
        {/* Command Center */}
        <Card className="mb-8 border-slate-200 shadow-lg bg-white/90 backdrop-blur">
          <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-blue-50 to-indigo-50">
            <CardTitle className="text-xl flex items-center gap-2">
              Command Center
            </CardTitle>
          </CardHeader>
          <CardContent className="pt-6">
            <div className="flex gap-4">
              <Input
                placeholder="Enter ticker symbol (e.g., AAPL, MSFT, TSLA)"
                value={ticker}
                onChange={(e) => setTicker(e.target.value.toUpperCase())}
                onKeyPress={(e) => e.key === 'Enter' && handleQuery()}
                className="text-lg h-12 border-slate-300 focus:border-blue-500 focus:ring-2 focus:ring-blue-500/20"
              />
              <Button
                onClick={handleQuery}
                disabled={loading || !ticker}
                className="h-12 px-8 bg-gradient-to-r from-blue-600 to-indigo-600 hover:from-blue-700 hover:to-indigo-700 shadow-md hover:shadow-lg transition-all"
              >
                {loading ? (
                  <span className="flex items-center gap-2">
                    Loading...
                  </span>
                ) : (
                  <span className="flex items-center gap-2">
                    Query
                  </span>
                )}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Compliance Status */}
        {complianceData && (
          <Card className={`mb-8 border-2 shadow-lg ${
            complianceData.compliance_status === 'APPROVED'
              ? 'border-green-200 bg-gradient-to-br from-green-50 to-emerald-50'
              : 'border-red-200 bg-gradient-to-br from-red-50 to-orange-50'
          }`}>
            <CardHeader className="border-b border-slate-200 bg-white/50">
              <div className="flex items-center justify-between">
                <CardTitle className="text-xl flex items-center gap-2">
                  Compliance Status
                </CardTitle>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowComplianceDetails(!showComplianceDetails)}
                  className="shadow-sm hover:shadow-md transition-all"
                >
                  {showComplianceDetails ? 'Hide Details' : 'View Compliance Details'}
                </Button>
              </div>
            </CardHeader>
            <CardContent className="pt-6">
              <div className="space-y-4">
                <div className="space-y-3">
                  <div className="flex items-center gap-3">
                    <Badge
                      className={`text-sm py-1.5 px-4 shadow-md ${
                        complianceData.compliance_status === 'APPROVED'
                          ? 'bg-gradient-to-r from-green-600 to-emerald-600'
                          : 'bg-gradient-to-r from-red-600 to-orange-600'
                      }`}
                    >
                      {complianceData.compliance_status}
                    </Badge>
                    <span className="text-lg font-semibold text-slate-700">
                      {complianceData.ticker}
                    </span>
                    {complianceData.risk_level && (
                      <Badge
                        variant={complianceData.risk_level === 'HIGH' ? 'destructive' : 'outline'}
                        className="shadow-sm"
                      >
                        Risk: {complianceData.risk_level}
                      </Badge>
                    )}
                  </div>
                  {complianceData.compliance_reason && (
                    <p className="text-sm text-slate-700 font-medium bg-white/60 p-3 rounded-lg">
                      {complianceData.compliance_reason}
                    </p>
                  )}
                  <div className="flex items-center gap-3 text-xs text-slate-600">
                    {complianceData.compliance_level && (
                      <span className="bg-white/60 px-3 py-1 rounded-full font-medium">
                        Level: {complianceData.compliance_level}
                      </span>
                    )}
                    <span className="bg-white/60 px-3 py-1 rounded-full">
                      {new Date(complianceData.compliance_checked_at).toLocaleString()}
                    </span>
                  </div>
                </div>

                {/* Detailed Compliance Breakdown */}
                {showComplianceDetails && (
                  <div className="border-t pt-4 space-y-4">
                    <div>
                      <h4 className="text-sm font-semibold mb-2">Multi-Layer Compliance Screening</h4>

                      {/* Checks Performed */}
                      {complianceData.checks_performed && complianceData.checks_performed.length > 0 && (
                        <div className="mb-4">
                          <p className="text-xs font-medium text-gray-700 mb-1">Checks Performed:</p>
                          <ul className="space-y-1">
                            {complianceData.checks_performed.map((check, idx) => (
                              <li key={idx} className="text-xs text-gray-600">{check}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Watchlist Alerts */}
                      {complianceData.watchlist_alerts && complianceData.watchlist_alerts.length > 0 && (
                        <div className="mb-4 p-3 bg-yellow-50 border border-yellow-200 rounded">
                          <p className="text-xs font-semibold text-yellow-900 mb-2">Watchlist Alerts:</p>
                          <ul className="space-y-1">
                            {complianceData.watchlist_alerts.map((alert, idx) => (
                              <li key={idx} className="text-xs text-yellow-800">{alert}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Ownership Concerns */}
                      {complianceData.ownership_concerns && complianceData.ownership_concerns.length > 0 && (
                        <div className="mb-4 p-3 bg-orange-50 border border-orange-200 rounded">
                          <p className="text-xs font-semibold text-orange-900 mb-2">Ownership Structure Concerns:</p>
                          <ul className="space-y-1">
                            {complianceData.ownership_concerns.map((concern, idx) => (
                              <li key={idx} className="text-xs text-orange-800">{concern}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Next Steps */}
                      {complianceData.next_steps && complianceData.next_steps.length > 0 && (
                        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded">
                          <p className="text-xs font-semibold text-red-900 mb-2">Required Actions:</p>
                          <ul className="space-y-1 list-disc list-inside">
                            {complianceData.next_steps.map((step, idx) => (
                              <li key={idx} className="text-xs text-red-800">{step}</li>
                            ))}
                          </ul>
                        </div>
                      )}

                      {/* Escalation Required */}
                      {complianceData.escalation_required && (
                        <div className="p-3 bg-red-100 border border-red-300 rounded">
                          <p className="text-xs font-semibold text-red-900">Escalation Required</p>
                          <p className="text-xs text-red-800 mt-1">
                            This ticker requires senior compliance officer review before data access can be granted.
                          </p>
                        </div>
                      )}

                      {/* Approval Details */}
                      {complianceData.compliance_status === 'APPROVED' && complianceData.data_access_approved && (
                        <div className="p-3 bg-green-50 border border-green-200 rounded">
                          <p className="text-xs font-semibold text-green-900">Data Access Approved</p>
                          <p className="text-xs text-green-800 mt-1">
                            All compliance layers cleared. Market data retrieval authorized.
                          </p>
                        </div>
                      )}
                    </div>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        )}

        {/* Error Display */}
        {error && (
          <Card className="mb-8 border-2 border-red-300 bg-gradient-to-br from-red-50 to-orange-50 shadow-lg">
            <CardContent className="pt-6">
              <div className="flex items-center gap-3">
                <div>
                  <p className="text-sm font-bold text-red-900">Error</p>
                  <p className="text-sm text-red-800">{error}</p>
                </div>
              </div>
            </CardContent>
          </Card>
        )}

        {/* Market Data */}
        {marketData && !marketData.error && (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 mb-8">
            {/* Entity Info */}
            <Card className="border-slate-200 shadow-lg hover:shadow-xl transition-shadow bg-white/90 backdrop-blur">
              <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-blue-50 to-cyan-50">
                <CardTitle className="text-lg flex items-center gap-2">
                  Company Info
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div>
                    <p className="text-2xl font-bold">
                      {marketData.entity_information.entity_name || 'N/A'}
                    </p>
                    <p className="text-sm text-gray-600">
                      {marketData.entity_information.ticker}
                    </p>
                  </div>
                  {marketData.entity_information.sector && (
                    <p className="text-sm text-gray-600">
                      Sector: {marketData.entity_information.sector}
                    </p>
                  )}
                  {marketData.entity_information.industry && (
                    <p className="text-sm text-gray-600">
                      Industry: {marketData.entity_information.industry}
                    </p>
                  )}
                  <Badge variant="outline" className="text-xs">
                    {marketData.metadata.data_source}
                  </Badge>
                </div>
              </CardContent>
            </Card>

            {/* Price & Market Cap */}
            <Card className="border-slate-200 shadow-lg hover:shadow-xl transition-shadow bg-white/90 backdrop-blur">
              <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-emerald-50 to-green-50">
                <CardTitle className="text-lg flex items-center gap-2">
                  Market Metrics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-3">
                  <div>
                    <p className="text-sm text-gray-600">Current Price</p>
                    <p className="text-3xl font-bold">
                      ${marketData.market_metrics.current_price?.toFixed(2) || 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Market Cap</p>
                    <p className="text-lg font-semibold">
                      ${marketData.market_metrics.market_cap
                        ? (marketData.market_metrics.market_cap / 1e9).toFixed(2) + 'B'
                        : 'N/A'}
                    </p>
                  </div>
                  <div>
                    <p className="text-sm text-gray-600">Volume</p>
                    <p className="text-sm">
                      {marketData.market_metrics.volume?.toLocaleString() || 'N/A'}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Valuation Ratios */}
            <Card className="border-slate-200 shadow-lg hover:shadow-xl transition-shadow bg-white/90 backdrop-blur">
              <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-purple-50 to-pink-50">
                <CardTitle className="text-lg flex items-center gap-2">
                  Valuation Ratios
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Forward P/E:</span>
                    <span className="text-sm font-semibold">
                      {marketData.valuation_ratios.forward_pe?.toFixed(2) || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Trailing P/E:</span>
                    <span className="text-sm font-semibold">
                      {marketData.valuation_ratios.trailing_pe?.toFixed(2) || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Price to Book:</span>
                    <span className="text-sm font-semibold">
                      {marketData.valuation_ratios.price_to_book?.toFixed(2) || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">PEG Ratio:</span>
                    <span className="text-sm font-semibold">
                      {marketData.valuation_ratios.peg_ratio?.toFixed(2) || 'N/A'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Financial Health */}
            <Card className="border-slate-200 shadow-lg hover:shadow-xl transition-shadow bg-white/90 backdrop-blur">
              <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-teal-50 to-cyan-50">
                <CardTitle className="text-lg flex items-center gap-2">
                  Financial Health
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Profit Margin:</span>
                    <span className="text-sm font-semibold">
                      {marketData.financial_health.profit_margin
                        ? (marketData.financial_health.profit_margin * 100).toFixed(2) + '%'
                        : 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Operating Margin:</span>
                    <span className="text-sm font-semibold">
                      {marketData.financial_health.operating_margin
                        ? (marketData.financial_health.operating_margin * 100).toFixed(2) + '%'
                        : 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">ROE:</span>
                    <span className="text-sm font-semibold">
                      {marketData.financial_health.return_on_equity
                        ? (marketData.financial_health.return_on_equity * 100).toFixed(2) + '%'
                        : 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">ROA:</span>
                    <span className="text-sm font-semibold">
                      {marketData.financial_health.return_on_assets
                        ? (marketData.financial_health.return_on_assets * 100).toFixed(2) + '%'
                        : 'N/A'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Analyst Metrics */}
            <Card className="border-slate-200 shadow-lg hover:shadow-xl transition-shadow bg-white/90 backdrop-blur">
              <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-orange-50 to-amber-50">
                <CardTitle className="text-lg flex items-center gap-2">
                  Analyst Metrics
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Target Price:</span>
                    <span className="text-sm font-semibold">
                      ${marketData.analyst_metrics.target_mean_price?.toFixed(2) || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Recommendation:</span>
                    <span className="text-sm font-semibold">
                      {marketData.analyst_metrics.recommendation_mean?.toFixed(2) || 'N/A'}
                    </span>
                  </div>
                  <div className="flex justify-between">
                    <span className="text-sm text-gray-600">Analyst Opinions:</span>
                    <span className="text-sm font-semibold">
                      {marketData.analyst_metrics.number_of_analyst_opinions || 'N/A'}
                    </span>
                  </div>
                </div>
              </CardContent>
            </Card>

            {/* Metadata */}
            <Card className="border-slate-200 shadow-lg hover:shadow-xl transition-shadow bg-white/90 backdrop-blur">
              <CardHeader className="border-b border-slate-100 bg-gradient-to-r from-indigo-50 to-violet-50">
                <CardTitle className="text-lg flex items-center gap-2">
                  Data Provenance
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="space-y-2">
                  <div>
                    <p className="text-xs text-gray-600">Source</p>
                    <Badge variant="default" className="text-xs">
                      {marketData.metadata.data_source}
                    </Badge>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600">Retrieved</p>
                    <p className="text-xs font-mono">
                      {new Date(marketData.metadata.retrieved_at).toLocaleString()}
                    </p>
                  </div>
                  <div>
                    <p className="text-xs text-gray-600">Ticker</p>
                    <p className="text-sm font-semibold">{marketData.metadata.ticker}</p>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        )}
      </div>

      {/* Footer */}
      <footer className="border-t border-slate-200 bg-white/80 backdrop-blur-md py-6 mt-12 shadow-lg">
        <div className="max-w-7xl mx-auto px-4">
          <div className="flex flex-col md:flex-row items-center justify-between gap-4">
            <div className="text-center md:text-left">
              <p className="text-sm font-semibold text-slate-700">
                Financial Intelligence MCP Server
              </p>
              <p className="text-xs text-slate-600 mt-1">
                Multi-Layer Compliance · Real-Time Data · Production Ready
              </p>
            </div>
            <div className="flex items-center gap-3">
              <Badge className="text-xs bg-gradient-to-r from-blue-600 to-indigo-600 shadow-sm">
                Real-Time Data
              </Badge>
              <Badge variant="outline" className="text-xs border-green-300 text-green-700">
                Compliance Verified
              </Badge>
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
}
