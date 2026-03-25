"""Simple HTTP server for py-invest web dashboard."""

import asyncio
import json
import sqlite3
import sys
import threading
from datetime import date, datetime, timedelta
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from typing import Any

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Get database path
DB_PATH = Path.home() / ".py-invest" / "data.db"
WEB_DIR = Path(__file__).parent


class DateEncoder(json.JSONEncoder):
    """JSON encoder for datetime objects."""

    def default(self, obj):
        if isinstance(obj, (date, datetime)):
            return obj.isoformat()
        return super().default(obj)


class DashboardHandler(SimpleHTTPRequestHandler):
    """HTTP request handler for dashboard."""

    def __init__(self, *args, auto_analyzer=None, **kwargs):
        self.auto_analyzer = auto_analyzer
        super().__init__(*args, directory=WEB_DIR, **kwargs)

    def log_message(self, format, *args):
        """Suppress default logging."""
        pass

    def do_DELETE(self):
        """Handle DELETE requests."""
        if self.path == '/api/reports':
            self._handle_delete_all_reports()
        else:
            self.send_error(404)

    def do_POST(self):
        """Handle POST requests."""
        if self.path == '/api/analyze':
            self._handle_trigger_analysis()
        else:
            self.send_error(404)

    def do_GET(self):
        """Handle GET requests."""
        parsed = self.path.split('?')[0]

        # API endpoints
        if parsed == '/api/stocks':
            self._handle_api_stocks()
        elif parsed == '/api/reports':
            self._handle_api_reports()
        elif parsed.startswith('/api/report/'):
            stock_code = parsed.split('/')[-1]
            self._handle_api_report(stock_code)
        elif parsed == '/api/status':
            self._handle_api_status()
        else:
            # Serve static files
            if parsed == '/':
                self.path = '/index.html'
            return super().do_GET()

    def _handle_delete_all_reports(self):
        """Delete all reports."""
        try:
            from storage import delete_all_reports
            count = delete_all_reports()
            self._send_json({"success": True, "deleted": count})
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, status=500)

    def _handle_trigger_analysis(self):
        """Trigger analysis for all active stocks."""
        try:
            if self.auto_analyzer:
                self.auto_analyzer.trigger_analysis()
                self._send_json({"success": True, "message": "Analysis triggered"})
            else:
                self._send_json({"success": False, "error": "Analyzer not available"}, status=503)
        except Exception as e:
            self._send_json({"success": False, "error": str(e)}, status=500)

    def _handle_api_status(self):
        """Get server status including analysis progress."""
        try:
            status = {
                "auto_analysis": self.auto_analyzer.is_running if self.auto_analyzer else False,
                "queue_size": self.auto_analyzer.queue_size if self.auto_analyzer else 0,
            }
            self._send_json(status)
        except Exception as e:
            self._send_json({"error": str(e)}, status=500)

    def _handle_api_stocks(self):
        """Get list of configured stocks."""
        try:
            if not DB_PATH.exists():
                self._send_json({"stocks": [], "error": "Database not found"})
                return

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT stock_code, stock_name, is_active FROM stock_configs WHERE is_active = 1"
            )
            rows = cursor.fetchall()
            conn.close()

            stocks = [
                {"code": row[0], "name": row[1] or row[0], "active": bool(row[2])}
                for row in rows
            ]
            self._send_json({"stocks": stocks})
        except Exception as e:
            self._send_json({"stocks": [], "error": str(e)})

    def _handle_api_reports(self):
        """Get latest reports for all stocks."""
        try:
            if not DB_PATH.exists():
                self._send_json({"reports": []})
                return

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()

            # Get latest report for each stock
            cursor.execute("""
                SELECT r.stock_code, r.report_date, r.analysis_json
                FROM daily_reports r
                INNER JOIN (
                    SELECT stock_code, MAX(report_date) as max_date
                    FROM daily_reports
                    GROUP BY stock_code
                ) latest ON r.stock_code = latest.stock_code AND r.report_date = latest.max_date
            """)
            rows = cursor.fetchall()
            conn.close()

            reports = []
            for row in rows:
                try:
                    data = json.loads(row[2])
                    reports.append(self._format_report(data))
                except:
                    continue

            self._send_json({"reports": reports})
        except Exception as e:
            self._send_json({"reports": [], "error": str(e)})

    def _handle_api_report(self, stock_code: str):
        """Get report for specific stock."""
        try:
            if not DB_PATH.exists():
                self._send_json({"error": "Database not found"})
                return

            conn = sqlite3.connect(DB_PATH)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT analysis_json FROM daily_reports WHERE stock_code = ? ORDER BY report_date DESC LIMIT 1",
                (stock_code,)
            )
            row = cursor.fetchone()
            conn.close()

            if row:
                data = json.loads(row[0])
                self._send_json({"report": self._format_report(data)})
            else:
                self._send_json({"error": "Report not found"})
        except Exception as e:
            self._send_json({"error": str(e)})

    def _send_json(self, data: dict, status: int = 200):
        """Send JSON response."""
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
        self.wfile.write(json.dumps(data, cls=DateEncoder, ensure_ascii=False).encode('utf-8'))

    def _format_report(self, data: dict) -> dict:
        """Format report data for frontend."""
        raw_data = data.get('raw_data', {})
        price_data = raw_data.get('query_stock_price', {}) if isinstance(raw_data, dict) else {}
        metrics_data = raw_data.get('query_financial_metrics', {}) if isinstance(raw_data, dict) else {}
        kline_data = raw_data.get('query_kline_data', {}) if isinstance(raw_data, dict) else {}

        # Extract price from raw_data or calculate from kline
        price = price_data.get('current_price', 0)
        change = price_data.get('change', 0)
        change_percent = price_data.get('change_percent', 0)

        # Fallback: get last close from kline data
        if not price and kline_data.get('data'):
            kline = kline_data['data']
            if isinstance(kline, list) and len(kline) > 0:
                last_day = kline[-1]
                if isinstance(last_day, dict):
                    price = last_day.get('close', 0)

        # Extract metrics with fallbacks
        pe = metrics_data.get('pe_ratio', '-')
        pb = metrics_data.get('pb_ratio', '-')
        market_cap = metrics_data.get('market_cap', '-')

        # Try to extract from sections if raw_data is empty
        sections = data.get('sections', [])
        section_dict = {s.get('title', ''): s.get('content', '') for s in sections}

        # Get technical and fundamental from sections
        technical = self._extract_section(data, '技术分析') or section_dict.get('Technical Picture', '')
        fundamental = self._extract_section(data, '基本面分析') or section_dict.get('Fundamental Analysis', '')
        risk = self._extract_section(data, '风险') or section_dict.get('Risk Factors', '')
        sector = self._extract_section(data, '行业') or section_dict.get('Sector & Comparables', '')

        return {
            "code": data.get('stock_code', ''),
            "name": data.get('stock_name', ''),
            "price": price,
            "change": change,
            "changePercent": change_percent,
            "rating": data.get('rating', 'hold').lower(),
            "confidence": data.get('confidence', 'medium').lower(),
            "targetPrice": data.get('target_price', 0),
            "summary": data.get('summary', ''),
            "metrics": {
                "pe": pe,
                "pb": pb,
                "marketCap": market_cap,
                "dividendYield": metrics_data.get('dividend_yield', '-')
            },
            "analysis": {
                "technical": technical,
                "fundamental": fundamental,
                "risk": risk,
                "sector": sector
            },
            "scenarios": {
                "bull": data.get('bull_case', ''),
                "bear": data.get('bear_case', ''),
                "base": data.get('base_case', '')
            }
        }

    def _extract_section(self, data: dict, keyword: str) -> str:
        """Extract section content from report sections."""
        sections = data.get('sections', [])
        for section in sections:
            if keyword in section.get('title', ''):
                return section.get('content', '')
        return ''


class AutoAnalyzer:
    """Background analyzer that automatically generates reports on startup."""

    def __init__(self):
        self.is_running = False
        self.queue_size = 0
        self._thread = None
        self._stop_event = threading.Event()

    def start(self):
        """Start the background analyzer thread."""
        if self._thread is None or not self._thread.is_alive():
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._run, daemon=True)
            self._thread.start()
            print("🔄 Auto-analyzer started")

    def stop(self):
        """Stop the background analyzer."""
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=5)
        print("🛑 Auto-analyzer stopped")

    def trigger_analysis(self):
        """Trigger analysis for all active stocks."""
        if not self.is_running:
            threading.Thread(target=self._analyze_all, daemon=True).start()

    def _run(self):
        """Main loop - check for missing reports and generate them."""
        import time

        # Wait a bit for server to fully start
        time.sleep(2)

        while not self._stop_event.is_set():
            try:
                self._analyze_all()
                # Check every 5 minutes
                for _ in range(300):
                    if self._stop_event.is_set():
                        break
                    time.sleep(1)
            except Exception as e:
                print(f"Auto-analyzer error: {e}")
                time.sleep(60)

    def _analyze_all(self):
        """Analyze all active stocks that don't have today's report."""
        try:
            from storage import get_active_stocks, get_report

            stocks = get_active_stocks()
            today = date.today()

            missing_stocks = []
            for stock in stocks:
                existing = get_report(stock.stock_code, today)
                if not existing:
                    missing_stocks.append(stock)

            if not missing_stocks:
                return

            self.queue_size = len(missing_stocks)
            self.is_running = True

            print(f"📊 Auto-analyzing {len(missing_stocks)} stocks...")

            # Process each stock
            for i, stock in enumerate(missing_stocks, 1):
                if self._stop_event.is_set():
                    break

                print(f"  [{i}/{len(missing_stocks)}] Analyzing {stock.stock_code}...")
                self._analyze_single(stock)
                self.queue_size = len(missing_stocks) - i

                # Small delay between stocks
                import time
                time.sleep(1)

            print("✅ Auto-analysis complete")

        except Exception as e:
            print(f"Analysis error: {e}")
        finally:
            self.is_running = False
            self.queue_size = 0

    def _analyze_single(self, stock_config):
        """Analyze a single stock."""
        try:
            import asyncio

            # Create new event loop for this thread
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            loop.run_until_complete(self._async_analyze(stock_config))
            loop.close()
        except Exception as e:
            print(f"Failed to analyze {stock_config.stock_code}: {e}")

    async def _async_analyze(self, stock_config):
        """Async analysis of a single stock."""
        try:
            from agents.orchestrator import SimpleAgentOrchestrator
            from storage import save_analysis_task, update_task_status
            from datetime import date
            import json

            # Create analysis task
            task_id = save_analysis_task(
                stock_code=stock_config.stock_code,
                stock_name=stock_config.stock_name,
                priority=0
            )

            update_task_status(task_id, "running")

            # Run analysis
            orchestrator = SimpleAgentOrchestrator(lang="zh")
            state = await orchestrator.analyze(
                stock_config.stock_code,
                "综合分析"
            )

            if state.report:
                from modules.report_generator.formatter import ReportFormatter, ReportFormat
                from storage import save_report

                # Convert to dict and save
                report_dict = json.loads(
                    ReportFormatter.format(state.report, ReportFormat.JSON)
                )
                report_dict["stock_name"] = stock_config.stock_name or state.report.stock_name

                save_report(
                    stock_code=stock_config.stock_code,
                    report_date=date.today(),
                    analysis_json=json.dumps(report_dict, ensure_ascii=False),
                )

                update_task_status(task_id, "completed")
                print(f"    ✓ {stock_config.stock_code} saved")
            else:
                update_task_status(task_id, "failed", error_message="No report generated")
                print(f"    ✗ {stock_config.stock_code} failed")

        except Exception as e:
            print(f"    ✗ {stock_config.stock_code} error: {e}")


def main():
    """Run the server."""
    import sys
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8080

    # Create auto-analyzer
    auto_analyzer = AutoAnalyzer()
    auto_analyzer.start()

    # Create server with custom handler factory
    def handler_factory(*args, **kwargs):
        return DashboardHandler(*args, auto_analyzer=auto_analyzer, **kwargs)

    server = HTTPServer(('localhost', port), handler_factory)
    print(f"🚀 Dashboard server running at http://localhost:{port}")
    print(f"📁 Serving files from: {WEB_DIR}")
    print("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\n👋 Shutting down...")
        auto_analyzer.stop()
        server.shutdown()


if __name__ == '__main__':
    main()
