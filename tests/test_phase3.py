import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPORT_DIR = ROOT / "analysis" / "export"

def test_market_export():
    p = EXPORT_DIR / "market.json"
    assert p.exists()
    data = json.loads(p.read_text())
    assert "total_2025" in data
    assert "total_2030" in data
    assert "overall_cagr" in data
    assert "workloads_2025" in data
    assert "deployments_2025" in data
    assert "assumptions" in data
    assert len(data["assumptions"]) > 0

def test_competitive_export():
    p = EXPORT_DIR / "competitive.json"
    assert p.exists()
    data = json.loads(p.read_text())
    assert "vendors" in data
    assert "capabilities" in data
    assert "scores" in data
    assert "positioning" in data
    assert len(data["vendors"]) == 6

def test_pipeline_export():
    p = EXPORT_DIR / "pipeline.json"
    assert p.exists()
    data = json.loads(p.read_text())
    assert "win_rate_by_competitor" in data
    assert "loss_reason_by_competitor" in data
    assert "stage_conversion" in data
    assert "churn_by_usage_decile" in data
    assert "delivery_velocity" in data
