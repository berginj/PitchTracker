"""Generate analysis reports in various formats."""

from pathlib import Path
from typing import Optional
import json
from .schemas import PatternAnalysisReport


def generate_json_report(report: PatternAnalysisReport, output_path: Path) -> None:
    """Generate JSON report file.
    
    Args:
        report: PatternAnalysisReport object
        output_path: Path to save JSON file
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    with open(output_path, 'w') as f:
        json.dump(report.to_dict(), f, indent=2)


def generate_html_report(report: PatternAnalysisReport, output_path: Path) -> None:
    """Generate HTML report with charts.
    
    Args:
        report: PatternAnalysisReport object
        output_path: Path to save HTML file
    """
    # Build pitch repertoire section
    repertoire_html = ""
    for rep in report.pitch_repertoire:
        repertoire_html += f"""
        <tr>
            <td>{rep.pitch_type}</td>
            <td>{rep.count}</td>
            <td>{rep.percentage:.1f}%</td>
            <td>{rep.avg_speed_mph:.1f} mph</td>
        </tr>
        """
    
    # Build anomalies section
    anomalies_html = ""
    if report.anomalies:
        for anomaly in report.anomalies:
            severity_color = {
                "low": "#FFC107",
                "medium": "#FF9800",
                "high": "#F44336"
            }.get(anomaly.severity, "#9E9E9E")
            
            anomalies_html += f"""
            <div style='background: {severity_color}20; border-left: 4px solid {severity_color}; 
                        padding: 10px; margin: 10px 0;'>
                <strong>{anomaly.anomaly_type.replace('_', ' ').title()}</strong> 
                (Severity: {anomaly.severity})<br>
                <em>{anomaly.recommendation}</em>
            </div>
            """
    else:
        anomalies_html = "<p>No anomalies detected.</p>"
    
    html = f"""<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Pattern Analysis Report - {report.session_id}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            max-width: 1000px;
            margin: 40px auto;
            padding: 20px;
            background-color: #f5f5f5;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            border-radius: 10px;
            margin-bottom: 30px;
        }}
        .summary {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 15px;
            margin-bottom: 30px;
        }}
        .summary-card {{
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
            text-align: center;
        }}
        .summary-card h3 {{
            margin: 0 0 10px 0;
            font-size: 32pt;
            color: #667eea;
        }}
        .summary-card p {{
            margin: 0;
            color: #666;
        }}
        .section {{
            background: white;
            padding: 25px;
            border-radius: 10px;
            margin-bottom: 20px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 15px 0;
        }}
        th, td {{
            padding: 12px;
            text-align: left;
            border-bottom: 1px solid #ddd;
        }}
        th {{
            background-color: #667eea;
            color: white;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⚾ Pattern Analysis Report</h1>
        <p><strong>Session:</strong> {report.session_id}</p>
        <p><strong>Generated:</strong> {report.created_utc}</p>
        {f"<p><strong>Pitcher:</strong> {report.pitcher_id}</p>" if report.pitcher_id else ""}
    </div>
    
    <div class="summary">
        <div class="summary-card">
            <h3>{report.total_pitches}</h3>
            <p>Total Pitches</p>
        </div>
        <div class="summary-card">
            <h3>{report.pitch_types_detected}</h3>
            <p>Pitch Types</p>
        </div>
        <div class="summary-card">
            <h3>{report.average_velocity_mph:.1f}</h3>
            <p>Avg Velocity (mph)</p>
        </div>
        <div class="summary-card">
            <h3>{report.strike_percentage:.0f}%</h3>
            <p>Strike %</p>
        </div>
        <div class="summary-card">
            <h3>{report.anomalies_detected}</h3>
            <p>Anomalies</p>
        </div>
    </div>
    
    <div class="section">
        <h2>Pitch Repertoire</h2>
        <table>
            <tr>
                <th>Pitch Type</th>
                <th>Count</th>
                <th>Percentage</th>
                <th>Avg Speed</th>
            </tr>
            {repertoire_html}
        </table>
    </div>
    
    <div class="section">
        <h2>Anomalies Detected</h2>
        {anomalies_html}
    </div>
    
    <div class="section">
        <h2>Consistency Metrics</h2>
        <p><strong>Velocity Std Dev:</strong> {report.consistency_metrics.velocity_std_mph:.2f} mph</p>
        <p><strong>Movement Consistency:</strong> {report.consistency_metrics.movement_consistency_score:.2f}</p>
    </div>
</body>
</html>"""
    
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding='utf-8')
