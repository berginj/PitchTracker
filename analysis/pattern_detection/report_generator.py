"""Generate analysis reports in various formats."""

import base64
from io import BytesIO
from pathlib import Path
import json

import matplotlib
matplotlib.use('Agg')  # Non-interactive backend
import matplotlib.pyplot as plt
import numpy as np

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


def _create_velocity_chart(report: PatternAnalysisReport) -> str:
    """Create velocity analysis chart and return as base64 PNG."""
    fig, ax = plt.subplots(figsize=(8, 5))

    # Extract velocity data from classifications
    velocities = [c.features.get('speed_mph', 0) for c in report.pitch_classifications]
    pitch_numbers = list(range(1, len(velocities) + 1))

    ax.plot(pitch_numbers, velocities, marker='o', linewidth=2, markersize=6)
    ax.set_xlabel('Pitch Number', fontsize=12)
    ax.set_ylabel('Velocity (mph)', fontsize=12)
    ax.set_title('Velocity Analysis', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3)

    # Save to base64
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'


def _create_movement_chart(report: PatternAnalysisReport) -> str:
    """Create movement profile chart and return as base64 PNG."""
    fig, ax = plt.subplots(figsize=(8, 6))

    # Extract movement data by pitch type
    pitch_types = {}
    for i, classification in enumerate(report.pitch_classifications):
        pitch_type = classification.heuristic_type
        run_in = classification.features.get('run_in', 0)
        rise_in = classification.features.get('rise_in', 0)

        if pitch_type not in pitch_types:
            pitch_types[pitch_type] = {'run': [], 'rise': []}

        pitch_types[pitch_type]['run'].append(run_in)
        pitch_types[pitch_type]['rise'].append(rise_in)

    # Plot each pitch type with different color
    colors = plt.cm.tab10.colors
    for idx, (pitch_type, data) in enumerate(pitch_types.items()):
        ax.scatter(data['run'], data['rise'], label=pitch_type,
                  s=100, alpha=0.6, color=colors[idx % len(colors)])

    ax.set_xlabel('Horizontal Break (in)', fontsize=12)
    ax.set_ylabel('Vertical Break (in)', fontsize=12)
    ax.set_title('Movement Profile', fontsize=14, fontweight='bold')
    ax.axhline(y=0, color='k', linestyle='--', alpha=0.3)
    ax.axvline(x=0, color='k', linestyle='--', alpha=0.3)
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Save to base64
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'


def _create_strike_zone_heatmap(report: PatternAnalysisReport) -> str:
    """Create strike zone heatmap and return as base64 PNG."""
    fig, ax = plt.subplots(figsize=(6, 6))

    # Create 3x3 heatmap (placeholder with dummy data since we don't have zone_row/zone_col)
    heatmap_data = np.zeros((3, 3))

    # Try to extract zone data from classifications (if available)
    # For now, just create a basic visualization

    im = ax.imshow(heatmap_data, cmap='YlOrRd', interpolation='nearest', vmin=0, vmax=max(1, heatmap_data.max()))

    # Add text annotations
    for i in range(3):
        for j in range(3):
            text = ax.text(j, i, int(heatmap_data[i, j]),
                          ha="center", va="center", color="black", fontsize=14)

    ax.set_xticks([0, 1, 2])
    ax.set_yticks([0, 1, 2])
    ax.set_xticklabels(['Outside', 'Middle', 'Inside'])
    ax.set_yticklabels(['High', 'Middle', 'Low'])
    ax.set_title('Strike Zone Distribution', fontsize=14, fontweight='bold')

    # Add colorbar
    cbar = plt.colorbar(im, ax=ax)
    cbar.set_label('Pitch Count', rotation=270, labelpad=15)

    # Save to base64
    buf = BytesIO()
    fig.savefig(buf, format='png', dpi=100, bbox_inches='tight')
    buf.seek(0)
    img_base64 = base64.b64encode(buf.read()).decode('utf-8')
    plt.close(fig)

    return f'data:image/png;base64,{img_base64}'


def generate_html_report(report: PatternAnalysisReport, output_path: Path) -> None:
    """Generate HTML report with charts.

    Args:
        report: PatternAnalysisReport object
        output_path: Path to save HTML file
    """
    # Generate charts
    velocity_chart = _create_velocity_chart(report)
    movement_chart = _create_movement_chart(report)
    strike_zone_chart = _create_strike_zone_heatmap(report)

    # Build pitch classification table
    classification_rows = ""
    for c in report.pitch_classifications:
        classification_rows += f"""
        <tr>
            <td>{c.pitch_id}</td>
            <td>{c.heuristic_type}</td>
            <td>{c.cluster_id if c.cluster_id is not None else 'N/A'}</td>
            <td>{c.confidence:.2f}</td>
            <td>{c.features.get('speed_mph', 0):.1f} mph</td>
        </tr>
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
        .chart {{
            text-align: center;
            margin: 20px 0;
        }}
        .chart img {{
            max-width: 100%;
            height: auto;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>⚾ Pattern Detection Analysis Report</h1>
        <p><strong>Session:</strong> {report.session_id}</p>
        <p><strong>Generated:</strong> {report.created_utc}</p>
        {f"<p><strong>Pitcher:</strong> {report.pitcher_id}</p>" if report.pitcher_id else ""}
    </div>

    <h2 style="margin: 20px 0 15px 0;">Executive Summary</h2>

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
        <h2>Pitch Classification</h2>
        <table>
            <tr>
                <th>Pitch ID</th>
                <th>Type</th>
                <th>Cluster</th>
                <th>Confidence</th>
                <th>Speed</th>
            </tr>
            {classification_rows}
        </table>
    </div>

    <div class="section">
        <h2>Velocity Analysis</h2>
        <div class="chart">
            <img src="{velocity_chart}" alt="Velocity Analysis Chart">
        </div>
    </div>

    <div class="section">
        <h2>Movement Profile</h2>
        <div class="chart">
            <img src="{movement_chart}" alt="Movement Profile Chart">
        </div>
    </div>

    <div class="section">
        <h2>Strike Zone Distribution</h2>
        <div class="chart">
            <img src="{strike_zone_chart}" alt="Strike Zone Heatmap">
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
