from __future__ import annotations

from datetime import date
from io import BytesIO
from pathlib import Path

import pandas as pd

from .issuance import normalize_issuance, upcoming_issuance
from .paths import output_dir
from .yield_curve import (
    latest_curve,
    term_spread,
    to_long_curve,
    with_daily_changes,
    yield_at_tenor,
)


KEY_TENORS = (1.0, 2.0, 5.0, 10.0, 30.0)


def _latest_change_table(curve_long: pd.DataFrame) -> pd.DataFrame:
    normalized = to_long_curve(curve_long)
    dates = sorted(normalized["date"].unique())
    latest_date = pd.Timestamp(dates[-1])
    previous_date = pd.Timestamp(dates[-2]) if len(dates) > 1 else None
    rows = []
    for tenor in KEY_TENORS:
        try:
            latest_yield, interpolated = yield_at_tenor(normalized, tenor, latest_date)
            previous_yield = None
            if previous_date is not None:
                previous_yield, _ = yield_at_tenor(normalized, tenor, previous_date)
            rows.append(
                {
                    "tenor_years": tenor,
                    "yield_pct": latest_yield,
                    "change_bp": (
                        None
                        if previous_yield is None
                        else (latest_yield - previous_yield) * 100.0
                    ),
                    "interpolated": interpolated,
                }
            )
        except ValueError:
            continue
    return pd.DataFrame(rows)


def generate_morning_brief(
    curve: pd.DataFrame,
    issuance: pd.DataFrame,
    news: pd.DataFrame,
    as_of: date | str | pd.Timestamp | None = None,
) -> str:
    curve_long = to_long_curve(curve)
    latest_date = curve_long["date"].max()
    report_date = pd.Timestamp(as_of or latest_date).date()
    changes = _latest_change_table(curve_long)
    upcoming = upcoming_issuance(issuance, report_date, days=7)
    news_frame = news.copy()
    if "date" in news_frame:
        news_frame["date"] = pd.to_datetime(news_frame["date"], errors="coerce")

    sources = sorted(curve_long["source"].dropna().astype(str).unique().tolist())
    source_text = "、".join(sources) if sources else "未标明"
    source_urls = (
        sorted(curve_long["source_url"].dropna().astype(str).unique().tolist())
        if "source_url" in curve_long
        else []
    )
    is_synthetic = any("synthetic" in source.lower() for source in sources)
    provenance_note = (
        "> 当前为合成示例数据，只用于离线演示，不构成投资建议。"
        if is_synthetic
        else f"> 收益率曲线来源：{source_text}；数值由结构化数据计算。"
    )

    lines = [
        f"# 债券市场晨报 {report_date:%Y-%m-%d}",
        "",
        provenance_note,
        *[f"> 来源链接：{url}" for url in source_urls],
        "> 一级发行和市场事件未接入官方数据时保持为空，不使用合成记录补齐。",
        "",
        "## 收益率曲线",
        "",
        "| 期限 | 收益率 | 日变动 |",
        "| ---: | ---: | ---: |",
    ]
    for row in changes.itertuples(index=False):
        tenor = f"{row.tenor_years:g}Y" + ("*" if row.interpolated else "")
        change = "N/A" if pd.isna(row.change_bp) else f"{row.change_bp:+.1f}BP"
        lines.append(f"| {tenor} | {row.yield_pct:.3f}% | {change} |")

    try:
        spread_2s10s = term_spread(curve_long, 2.0, 10.0)
        spread_5s10s = term_spread(curve_long, 5.0, 10.0)
        lines.extend(
            [
                "",
                f"2Y-10Y 期限利差为 **{spread_2s10s:.1f}BP**，"
                f"5Y-10Y 期限利差为 **{spread_5s10s:.1f}BP**。",
            ]
        )
        if changes["interpolated"].any():
            lines.append("带 * 的期限由相邻期限线性插值得到。")
    except ValueError:
        lines.extend(["", "关键期限不足，暂不计算期限利差。"])

    lines.extend(["", "## 未来七日一级发行", ""])
    if upcoming.empty:
        lines.append("暂无已录入的待发行债券。")
    else:
        for row in upcoming.itertuples(index=False):
            size = (
                "规模待定"
                if pd.isna(row.issue_size_billion)
                else f"{row.issue_size_billion:g}亿元"
            )
            lines.append(
                f"- {row.issue_date:%m-%d} {row.bond_name}：{row.term_years:g}年，"
                f"{size}，{row.bid_method}。"
            )

    lines.extend(["", "## 宏观与市场事件", ""])
    if news_frame.empty:
        lines.append("暂无已录入事件。")
    else:
        for row in news_frame.tail(6).itertuples(index=False):
            impact = getattr(row, "impact", "待评估")
            lines.append(f"- [{row.category}/{impact}] {row.title}")

    lines.extend(
        [
            "",
            "## 复核清单",
            "",
            "- 核对收益率曲线日期、单位与来源。",
            "- 核对发行规模、招标时间、招标方式和结果公告。",
            "- 大模型仅用于分类与文字初稿，不得覆盖结构化数值。",
        ]
    )
    return "\n".join(lines) + "\n"


def excel_bytes(
    curve: pd.DataFrame,
    issuance: pd.DataFrame,
    news: pd.DataFrame,
) -> bytes:
    curve_long = with_daily_changes(curve)
    issuance_clean = normalize_issuance(issuance)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        curve_long.to_excel(writer, sheet_name="收益率曲线", index=False)
        latest_curve(curve_long).to_excel(writer, sheet_name="最新曲线", index=False)
        issuance_clean.to_excel(writer, sheet_name="一级发行", index=False)
        news.to_excel(writer, sheet_name="市场事件", index=False)
        for sheet in writer.book.worksheets:
            sheet.freeze_panes = "A2"
            sheet.auto_filter.ref = sheet.dimensions
            for column_cells in sheet.columns:
                width = min(max(len(str(cell.value or "")) for cell in column_cells) + 2, 40)
                sheet.column_dimensions[column_cells[0].column_letter].width = width
    return buffer.getvalue()


def write_report_bundle(
    curve: pd.DataFrame,
    issuance: pd.DataFrame,
    news: pd.DataFrame,
    as_of: date | str | pd.Timestamp | None = None,
    destination: Path | None = None,
) -> tuple[Path, Path]:
    target = destination or output_dir()
    target.mkdir(parents=True, exist_ok=True)
    report_date = pd.Timestamp(as_of or to_long_curve(curve)["date"].max()).date()
    stem = f"fixed_income_brief_{report_date:%Y%m%d}"
    markdown_path = target / f"{stem}.md"
    workbook_path = target / f"{stem}.xlsx"
    markdown_path.write_text(
        generate_morning_brief(curve, issuance, news, report_date), encoding="utf-8"
    )
    workbook_path.write_bytes(excel_bytes(curve, issuance, news))
    return markdown_path, workbook_path
