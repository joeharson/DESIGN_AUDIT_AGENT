"""JSON and HTML report generation."""

from __future__ import annotations

import json
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

from core.audit_contracts import AuditReport
from core.comparison_audit_contracts import DiffReport
from core.regression_scan_contracts import ScanReport


def _template_environment() -> Environment:
    template_dir = Path(__file__).resolve().parents[1] / "templates"
    return Environment(
        loader=FileSystemLoader(template_dir),
        autoescape=select_autoescape(["html", "xml"]),
    )


def save_json_report(report: AuditReport, output_dir: str = "output") -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / f"audit_{report.report_id}.json"
    report.json_report_path = str(report_path)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return str(report_path)


def save_html_report(report: AuditReport, output_dir: str = "output") -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    html = _template_environment().get_template("audit_finding_report.html").render(report=report)
    report_path = output_path / f"audit_{report.report_id}.html"
    report.html_report_path = str(report_path)
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)


def save_diff_report_json(report: DiffReport, output_dir: str = "output") -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / f"diff_{report.report_id}.json"
    report.json_report_path = str(report_path)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return str(report_path)


def save_diff_report_html(report: DiffReport, output_dir: str = "output") -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    html = _template_environment().get_template("comparison_diff_report.html").render(report=report)
    report_path = output_path / f"diff_{report.report_id}.html"
    report.html_report_path = str(report_path)
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)


def save_scan_report_json(report: ScanReport, output_dir: str = "output/scans") -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    report_path = output_path / f"{report.scan_id}.json"
    report.json_report_path = str(report_path)
    report_path.write_text(
        json.dumps(report.model_dump(mode="json"), indent=2),
        encoding="utf-8",
    )
    return str(report_path)


def save_scan_report_html(report: ScanReport, output_dir: str = "output/scans") -> str:
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    html = _template_environment().get_template("regression_scan_report.html").render(report=report)
    report_path = output_path / f"{report.scan_id}.html"
    report.html_report_path = str(report_path)
    report_path.write_text(html, encoding="utf-8")
    return str(report_path)
