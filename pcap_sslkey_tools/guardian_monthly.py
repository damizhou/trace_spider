#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Guardian CSV 月度统计（零参数即可运行）
------------------------------------------------
做什么：
1) 递归读取脚本同目录下 theguardian_all_reformat/ 里的 guardian_*.csv
2) 从 URL 解析日期（支持 /YYYY/mmm/DD 与 /YYYY/MM/DD）
3) 仅统计 2024 年数据（按 Section × 月份计数）
4) 输出 Excel：Sheet1 为数据透视表，Sheet2 为折线图（每条线一个 Section）

依赖：
    pip install pandas xlsxwriter
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, List

import pandas as pd


# ===== 可改的默认项（不需要命令行参数） =====================================
BASE_DIR = Path(__file__).resolve().parent
INPUT_DIR = Path("/netdisk/theguardian_with_ssl_key/2024/theguardian_all_reformat")
OUTPUT_XLSX = BASE_DIR / "guardian_2024_monthly.xlsx"
TARGET_YEAR = 2024
LOG_LEVEL = logging.INFO  # 可改为 logging.DEBUG 看详细日志


# ===== 内部实现 ============================================================
MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# /2024/jan/31/ 或 /2024/jan/31
RE_DATE_ABBR = re.compile(r"/(?P<y>\d{4})/(?P<m>[a-z]{3})/(?P<d>\d{1,2})(?:/|$)")
# /2024/01/31/ 或 /2024/1/2
RE_DATE_NUM = re.compile(r"/(?P<y>\d{4})/(?P<m>\d{1,2})/(?P<d>\d{1,2})(?:/|$)")


@dataclass
class Config:
    input_dir: Path
    output_xlsx: Path
    year: int


def parse_url_date(url: str) -> Optional[date]:
    """从 Guardian 文章 URL 中解析日期。失败返回 None。"""
    if not isinstance(url, str):
        return None
    u = url.strip().lower()

    m = RE_DATE_ABBR.search(u)
    if m:
        y = int(m.group("y"))
        mm_abbr = m.group("m")
        mm = MONTH_ABBR.get(mm_abbr)
        dd = int(m.group("d"))
        if mm:
            try:
                return date(y, mm, dd)
            except ValueError:
                return None

    m = RE_DATE_NUM.search(u)
    if m:
        y = int(m.group("y"))
        mm = int(m.group("m"))
        dd = int(m.group("d"))
        try:
            return date(y, mm, dd)
        except ValueError:
            return None

    return None


def read_guardian_csv(csv_path: Path) -> pd.DataFrame:
    """
    读取单个 CSV -> DataFrame，只保留 ['section','url']，并解析 ['year','month']。
    自动识别分隔符（逗号/制表符）。
    """
    df = pd.read_csv(csv_path, sep=None, engine="python", dtype=str)
    df.columns = [c.strip().lower() for c in df.columns]

    required = {"section", "url"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path} 缺少必要列: {missing}")

    df = df[["section", "url"]].copy()

    parsed = df["url"].map(parse_url_date)
    df["year"] = parsed.map(lambda d: d.year if d else None)
    df["month"] = parsed.map(lambda d: d.month if d else None)

    df = df.dropna(subset=["year", "month"])
    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    return df


def build_pivot_monthly(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """生成 Section × 01..12 的月度计数透视表，缺失填 0。"""
    dfy = df[df["year"] == year].copy()
    if dfy.empty:
        return pd.DataFrame(columns=[f"{m:02d}" for m in range(1, 13)])

    grp = (
        dfy.groupby(["section", "month"], dropna=False)
           .size()
           .rename("count")
           .reset_index()
    )
    pivot = grp.pivot(index="section", columns="month", values="count").fillna(0).astype(int)

    # 补齐 12 个月
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = 0

    pivot = pivot.reindex(columns=sorted(pivot.columns))
    pivot.columns = [f"{m:02d}" for m in pivot.columns]
    pivot = pivot.sort_index()
    return pivot


def xl_cell(row0: int, col0: int) -> str:
    """(0-based) -> Excel 单元格标记，如 (0,0)->A1。"""
    col = col0
    letters: List[str] = []
    while True:
        col, rem = divmod(col, 26)
        letters.append(chr(ord('A') + rem))
        if col == 0:
            break
        col -= 1
    return f"{''.join(reversed(letters))}{row0 + 1}"


def write_excel_with_chart(pivot: pd.DataFrame, out_path: Path, year: int) -> None:
    """
    写 Excel：
      - Sheet1: Monthly_{year}（透视表 + Total 列）
      - Sheet2/3/4: 3 个折线图工作表（每张图最多 8 个 Section），每个数据点显示数值
    """
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        sheet_data = f"Monthly_{year}"
        pivot.to_excel(writer, sheet_name=sheet_data)
        wb = writer.book
        ws = writer.sheets[sheet_data]

        # 冻结、筛选与列宽
        ws.freeze_panes(1, 1)
        ws.autofilter(0, 0, pivot.shape[0], pivot.shape[1])
        ws.set_column(0, 0, 24)                 # Section 列
        ws.set_column(1, pivot.shape[1], 10)    # 01..12 列

        # 添加总计列（便于浏览，不参与绘图）
        n_rows, n_cols = pivot.shape
        ws.write(0, 1 + n_cols, "Total")
        for i in range(n_rows):
            r = 1 + i  # 数据的第 1 行在 Excel 是第 2 行
            ws.write_formula(r, 1 + n_cols, f"=SUM({xl_cell(r,1)}:{xl_cell(r,n_cols)})")

        # X 轴月份分类（B1..M1）
        categories = f"='{sheet_data}'!${xl_cell(0,1)}:${xl_cell(0,n_cols)}" if n_cols > 0 else None

        # 图表页
        sheet_chart = f"Chart_{year}"
        wsc = wb.add_worksheet(sheet_chart)
        chart = wb.add_chart({"type": "line"})
        chart.set_title({"name": f"Guardian {year} 每月数量（按 Section）"})
        chart.set_x_axis({"name": "月份 (01–12)"})
        chart.set_y_axis({"name": "数量"})
        chart.set_legend({"position": "bottom"})

        # X 轴（B1..M1）
        if n_cols > 0:
            categories = f"='{sheet_data}'!${xl_cell(0, 1)}:${xl_cell(0, n_cols)}"
        else:
            categories = None  # 空数据容错

        # 每个 Section 一条线
        for i in range(n_rows):
            row = 1 + i
            chart.add_series({"name": f"='{sheet_data}'!${xl_cell(row, 0)}", "categories": categories,
                              "values": f"='{sheet_data}'!${xl_cell(row, 1)}:${xl_cell(row, n_cols)}",
                              "data_labels": {"value": True}, })

        wsc.insert_chart("A1", chart, {"x_scale": 2.0, "y_scale": 1.6})

        # === 这里开始拆分 3 张图表，每张最多 8 个 Section ===
        SECTIONS_PER_CHART = 8
        NUM_CHARTS = 3

        for part_idx in range(NUM_CHARTS):
            start_idx = part_idx * SECTIONS_PER_CHART
            end_idx = min(start_idx + SECTIONS_PER_CHART, n_rows)
            if start_idx >= n_rows:
                # 没有更多的 Section 了，就不再创建图表工作表
                break

            sheet_chart = f"Chart_{year}_P{part_idx + 1}"
            wsc = wb.add_worksheet(sheet_chart)

            chart = wb.add_chart({"type": "line"})
            chart.set_title({"name": f"Guardian {year} 每月数量（按 Section）- 第 {part_idx + 1} 组"})
            chart.set_x_axis({"name": "月份 (01–12)"})
            chart.set_y_axis({"name": "数量"})
            chart.set_legend({"position": "bottom"})

            # 为该分组内的每个 Section 添加一条序列，并打开数据标签
            for row_idx in range(start_idx, end_idx):
                row_excel = 1 + row_idx  # 折线数据所在的 Excel 行（含表头偏移）
                chart.add_series({
                    "name":      f"='{sheet_data}'!${xl_cell(row_excel, 0)}",
                    "categories": categories,
                    "values":    f"='{sheet_data}'!${xl_cell(row_excel, 1)}:${xl_cell(row_excel, n_cols)}",
                    "data_labels": {"value": True},   # ★ 每个数据点显示数值
                    # 不指定颜色，交由 Excel 默认配色；也可按需添加 marker：
                    # "marker": {"type": "automatic"},
                })

            # 插入图表
            wsc.insert_chart("A1", chart, {"x_scale": 2.0, "y_scale": 1.6})






def run(cfg: Config) -> None:
    logging.info("输入目录：%s", cfg.input_dir)
    csv_files = sorted(cfg.input_dir.rglob("guardian_*.csv"))

    if not csv_files:
        logging.warning("未找到 CSV 文件，输出空模板：%s", cfg.output_xlsx)
        empty = pd.DataFrame(columns=[f"{m:02d}" for m in range(1, 13)])
        write_excel_with_chart(empty, cfg.output_xlsx, cfg.year)
        return

    frames = []
    for p in csv_files:
        try:
            df = read_guardian_csv(p)
            frames.append(df)
            logging.debug("读取 %s 行数=%d", p.name, len(df))
        except Exception as e:
            logging.error("读取失败：%s，原因：%s", p, e)

    if not frames:
        logging.warning("所有文件读取失败，输出空模板：%s", cfg.output_xlsx)
        empty = pd.DataFrame(columns=[f"{m:02d}" for m in range(1, 13)])
        write_excel_with_chart(empty, cfg.output_xlsx, cfg.year)
        return

    all_df = pd.concat(frames, ignore_index=True)
    pivot = build_pivot_monthly(all_df, cfg.year)
    write_excel_with_chart(pivot, cfg.output_xlsx, cfg.year)
    logging.info("完成：%s", cfg.output_xlsx)


def main() -> None:
    logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s: %(message)s")
    cfg = Config(input_dir=INPUT_DIR, output_xlsx=OUTPUT_XLSX, year=TARGET_YEAR)
    run(cfg)


if __name__ == "__main__":
    main()
