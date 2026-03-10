from __future__ import annotations

from datetime import datetime, timezone

from .models import DailyReport
from .repository import StateRepository


def generate_daily_report(repo: StateRepository, date: str) -> DailyReport:
    recommendations = repo.list_recommendations()

    lines: list[str] = []
    lines.append(f"# 基金舆情日报 {date}")
    lines.append("")
    lines.append("## 今日结论")
    for row in recommendations:
        lines.append(
            f"- {row.fund_name}({row.fund_code or 'PENDING'}): {row.action.upper()} | confidence={row.confidence:.2f} | up={row.up_probability:.2f} | down={row.down_probability:.2f}"
        )

    lines.append("")
    lines.append("## 变化原因")
    for row in recommendations:
        lines.append(f"- {row.fund_name}: {'; '.join(row.reasons)}")

    lines.append("")
    lines.append("## 风险提醒")
    for row in recommendations:
        lines.append(f"- {row.fund_name}: stop_profit={row.stop_profit}, stop_loss={row.stop_loss}")

    lines.append("")
    lines.append("## 明日观察点")
    for row in recommendations:
        lines.append(f"- {row.fund_name}: conflict={row.conflict_summary}")

    markdown = "\n".join(lines)
    html_items = "".join([f"<li>{line[2:]}</li>" for line in lines if line.startswith("- ")])
    html = f"<html><body><h1>基金舆情日报 {date}</h1><ul>{html_items}</ul></body></html>"

    report = DailyReport(date=date, markdown=markdown, html=html, generated_at=datetime.now(timezone.utc))
    repo.save_report(report)
    return report
