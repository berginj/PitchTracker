"""Report generation for pattern detection analysis."""

from __future__ import annotations

import base64
import json
from io import BytesIO
from pathlib import Path
from typing import TYPE_CHECKING, Dict, List, Optional

import matplotlib
import matplotlib.pyplot as plt
import numpy as np

# Use non-interactive backend for server-side generation
matplotlib.use('Agg')

from analysis.pattern_detection.schemas import AnalysisReport

if TYPE_CHECKING:
    from app.pipeline_service import PitchSummary


class ReportGenerator:
    """Generate JSON and HTML reports for pattern detection analysis."""

    def __init__(self):
        """Initialize report generator."""
        self.dpi = 100  # DPI for chart rendering

    def generate_json_report(
        self,
        report: AnalysisReport,
        output_path: Path
    ) -> None:
        """Generate JSON report file.

        Args:
            report: Analysis report
            output_path: Path to output JSON file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(report.to_dict(), f, indent=2)

    def generate_html_report(
        self,
        report: AnalysisReport,
        pitches: List["PitchSummary"],
        output_path: Path
    ) -> None:
        """Generate HTML report with embedded charts.

        Args:
            report: Analysis report
            pitches: List of pitch summaries (for chart data)
            output_path: Path to output HTML file
        """
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Generate charts
        velocity_chart = self._generate_velocity_chart(pitches, report.anomalies)
        movement_chart = self._generate_movement_chart(pitches, report.pitch_classification)
        heatmap_chart = self._generate_heatmap(pitches)
        repertoire_chart = self._generate_repertoire_chart(report.pitch_repertoire)

        # Build HTML
        html = self._build_html(report, velocity_chart, movement_chart, heatmap_chart, repertoire_chart)

        output_path.write_text(html)

    def _generate_velocity_chart(
        self,
        pitches: List["PitchSummary"],
        anomalies: List
    ) -> str:
        """Generate velocity line chart with anomalies highlighted.

        Args:
            pitches: List of pitch summaries
            anomalies: List of anomalies

        Returns:
            Base64-encoded PNG image
        """
        fig, ax = plt.subplots(figsize=(10, 6))

        pitch_numbers = list(range(1, len(pitches) + 1))
        velocities = [p.speed_mph if p.speed_mph is not None else 0.0 for p in pitches]

        # Plot velocities
        ax.plot(pitch_numbers, velocities, 'o-', color='#2196F3', linewidth=2, markersize=6, label='Velocity')

        # Highlight anomalies
        speed_anomaly_ids = {a.pitch_id for a in anomalies if 'speed' in a.anomaly_type.lower()}
        for i, pitch in enumerate(pitches):
            if pitch.pitch_id in speed_anomaly_ids:
                ax.plot(i+1, pitch.speed_mph if pitch.speed_mph else 0, 'ro', markersize=10,
                       label='Anomaly' if i == 0 else '')

        ax.set_xlabel('Pitch Number', fontsize=12)
        ax.set_ylabel('Velocity (mph)', fontsize=12)
        ax.set_title('Pitch Velocity Over Session', fontsize=14, fontweight='bold')
        ax.grid(True, alpha=0.3)
        ax.legend()

        return self._fig_to_base64(fig)

    def _generate_movement_chart(
        self,
        pitches: List["PitchSummary"],
        classifications: List
    ) -> str:
        """Generate movement scatter plot (run_in vs rise_in).

        Args:
            pitches: List of pitch summaries
            classifications: List of pitch classifications

        Returns:
            Base64-encoded PNG image
        """
        fig, ax = plt.subplots(figsize=(10, 8))

        # Group by pitch type
        pitch_types = {}
        for i, classification in enumerate(classifications):
            pitch_type = classification.heuristic_type
            if pitch_type not in pitch_types:
                pitch_types[pitch_type] = []
            pitch_types[pitch_type].append(i)

        # Plot each type with different color
        colors = plt.cm.tab10(np.linspace(0, 1, len(pitch_types)))

        for (pitch_type, indices), color in zip(pitch_types.items(), colors):
            runs = [pitches[i].run_in for i in indices if pitches[i].run_in is not None]
            rises = [pitches[i].rise_in for i in indices if pitches[i].rise_in is not None]

            if runs and rises:
                ax.scatter(runs, rises, s=100, alpha=0.6, c=[color], label=pitch_type, edgecolors='black')

        ax.set_xlabel('Horizontal Movement (inches)', fontsize=12)
        ax.set_ylabel('Vertical Movement (inches)', fontsize=12)
        ax.set_title('Pitch Movement Profile', fontsize=14, fontweight='bold')
        ax.axhline(y=0, color='k', linestyle='--', alpha=0.3)
        ax.axvline(x=0, color='k', linestyle='--', alpha=0.3)
        ax.grid(True, alpha=0.3)
        ax.legend(loc='best', framealpha=0.9)

        return self._fig_to_base64(fig)

    def _generate_heatmap(
        self,
        pitches: List["PitchSummary"]
    ) -> str:
        """Generate strike zone heatmap.

        Args:
            pitches: List of pitch summaries

        Returns:
            Base64-encoded PNG image
        """
        fig, ax = plt.subplots(figsize=(6, 6))

        # Create 3x3 heatmap
        heatmap = [[0]*3 for _ in range(3)]

        for pitch in pitches:
            if pitch.zone_row is not None and pitch.zone_col is not None:
                row = pitch.zone_row
                col = pitch.zone_col
                if 0 <= row < 3 and 0 <= col < 3:
                    heatmap[row][col] += 1

        # Plot heatmap
        im = ax.imshow(heatmap, cmap='YlOrRd', aspect='auto')

        # Add text annotations
        for i in range(3):
            for j in range(3):
                text = ax.text(j, i, str(heatmap[i][j]),
                             ha="center", va="center", color="black", fontsize=16, fontweight='bold')

        ax.set_xticks([0, 1, 2])
        ax.set_yticks([0, 1, 2])
        ax.set_xticklabels(['Left', 'Middle', 'Right'])
        ax.set_yticklabels(['High', 'Middle', 'Low'])
        ax.set_title('Strike Zone Heatmap', fontsize=14, fontweight='bold')

        plt.colorbar(im, ax=ax, label='Pitch Count')

        return self._fig_to_base64(fig)

    def _generate_repertoire_chart(
        self,
        repertoire: Dict
    ) -> str:
        """Generate pitch repertoire pie chart.

        Args:
            repertoire: Dictionary of pitch type statistics

        Returns:
            Base64-encoded PNG image
        """
        if not repertoire:
            # Return empty chart
            fig, ax = plt.subplots(figsize=(8, 6))
            ax.text(0.5, 0.5, 'No pitch type data available', ha='center', va='center', fontsize=14)
            ax.axis('off')
            return self._fig_to_base64(fig)

        fig, ax = plt.subplots(figsize=(8, 6))

        labels = list(repertoire.keys())
        sizes = [r.count for r in repertoire.values()]
        colors = plt.cm.Set3(np.linspace(0, 1, len(labels)))

        wedges, texts, autotexts = ax.pie(sizes, labels=labels, colors=colors, autopct='%1.1f%%',
                                            startangle=90, textprops={'fontsize': 11})

        for autotext in autotexts:
            autotext.set_color('black')
            autotext.set_fontweight('bold')

        ax.set_title('Pitch Type Distribution', fontsize=14, fontweight='bold')

        return self._fig_to_base64(fig)

    def _fig_to_base64(self, fig) -> str:
        """Convert matplotlib figure to base64-encoded PNG.

        Args:
            fig: Matplotlib figure

        Returns:
            Base64-encoded data URI
        """
        buffer = BytesIO()
        fig.savefig(buffer, format='png', dpi=self.dpi, bbox_inches='tight')
        buffer.seek(0)
        img_base64 = base64.b64encode(buffer.read()).decode('utf-8')
        plt.close(fig)

        return f"data:image/png;base64,{img_base64}"

    def _build_html(
        self,
        report: AnalysisReport,
        velocity_chart: str,
        movement_chart: str,
        heatmap_chart: str,
        repertoire_chart: str
    ) -> str:
        """Build HTML report.

        Args:
            report: Analysis report
            velocity_chart: Base64-encoded velocity chart
            movement_chart: Base64-encoded movement chart
            heatmap_chart: Base64-encoded heatmap
            repertoire_chart: Base64-encoded repertoire chart

        Returns:
            HTML string
        """
        # Build anomaly table HTML
        anomaly_rows = ""
        for anomaly in report.anomalies:
            severity_color = {
                "high": "#f44336",
                "medium": "#ff9800",
                "low": "#ffeb3b"
            }.get(anomaly.severity, "#ccc")

            anomaly_rows += f"""
            <tr>
                <td>{anomaly.pitch_id}</td>
                <td>{anomaly.anomaly_type}</td>
                <td style="background-color: {severity_color}; color: black; font-weight: bold;">{anomaly.severity}</td>
                <td>{anomaly.recommendation}</td>
            </tr>
            """

        # Build baseline comparison HTML
        baseline_html = ""
        if report.baseline_comparison and report.baseline_comparison.profile_exists:
            bc = report.baseline_comparison
            if bc.velocity_vs_baseline:
                vel = bc.velocity_vs_baseline
                baseline_html += f"""
                <h3>Baseline Comparison</h3>
                <p><strong>Velocity:</strong> {vel['current']:.1f} mph (baseline: {vel['baseline']:.1f} mph,
                delta: {vel['delta_mph']:+.1f} mph) - Status: <strong>{vel['status']}</strong></p>
                """

        html = f"""
<!DOCTYPE html>
<html>
<head>
    <title>Pattern Detection Report - {report.session_id}</title>
    <style>
        body {{
            font-family: Arial, sans-serif;
            margin: 20px;
            background-color: #f5f5f5;
        }}
        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background-color: white;
            padding: 30px;
            box-shadow: 0 2px 4px rgba(0,0,0,0.1);
        }}
        h1 {{
            color: #2196F3;
            border-bottom: 3px solid #2196F3;
            padding-bottom: 10px;
        }}
        h2 {{
            color: #333;
            margin-top: 30px;
        }}
        .summary-box {{
            background-color: #e3f2fd;
            padding: 20px;
            border-radius: 5px;
            margin: 20px 0;
        }}
        .summary-box p {{
            margin: 10px 0;
            font-size: 16px;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            margin: 20px 0;
        }}
        th, td {{
            border: 1px solid #ddd;
            padding: 12px;
            text-align: left;
        }}
        th {{
            background-color: #2196F3;
            color: white;
            font-weight: bold;
        }}
        tr:nth-child(even) {{
            background-color: #f9f9f9;
        }}
        .chart {{
            margin: 30px 0;
            text-align: center;
        }}
        .chart img {{
            max-width: 100%;
            height: auto;
        }}
        .footer {{
            margin-top: 40px;
            text-align: center;
            color: #666;
            font-size: 12px;
        }}
    </style>
</head>
<body>
    <div class="container">
        <h1>Pattern Detection Analysis Report</h1>

        <div class="summary-box">
            <h2>Executive Summary</h2>
            <p><strong>Session:</strong> {report.session_id}</p>
            <p><strong>Generated:</strong> {report.created_utc}</p>
            <p><strong>Total Pitches:</strong> {report.summary.total_pitches}</p>
            <p><strong>Anomalies Detected:</strong> {report.summary.anomalies_detected}</p>
            <p><strong>Pitch Types Detected:</strong> {report.summary.pitch_types_detected}</p>
            <p><strong>Average Velocity:</strong> {report.summary.average_velocity_mph:.1f} mph</p>
            <p><strong>Strike Percentage:</strong> {report.summary.strike_percentage:.1%}</p>
        </div>

        {baseline_html}

        <h2>Pitch Classification</h2>
        <div class="chart">
            <img src="{repertoire_chart}" alt="Pitch Repertoire">
        </div>

        <h2>Velocity Analysis</h2>
        <div class="chart">
            <img src="{velocity_chart}" alt="Velocity Chart">
        </div>

        <h2>Movement Profile</h2>
        <div class="chart">
            <img src="{movement_chart}" alt="Movement Chart">
        </div>

        <h2>Strike Zone Distribution</h2>
        <div class="chart">
            <img src="{heatmap_chart}" alt="Strike Zone Heatmap">
        </div>

        <h2>Detected Anomalies</h2>
        <table>
            <tr>
                <th>Pitch ID</th>
                <th>Type</th>
                <th>Severity</th>
                <th>Recommendation</th>
            </tr>
            {anomaly_rows if anomaly_rows else '<tr><td colspan="4">No anomalies detected</td></tr>'}
        </table>

        <div class="footer">
            <p>Generated by PitchTracker Pattern Detection System</p>
            <p>Report Version: {report.schema_version}</p>
        </div>
    </div>
</body>
</html>
        """

        return html


__all__ = ["ReportGenerator"]
