#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
Guardian CSV 月度统计（2024）
--------------------------------
功能：
1) 递归读取目录下的 guardian_*.csv（默认 theguardian_all_reformat）
2) 从 URL 中解析日期（兼容 2024/jan/01 或 2024/01/01 等形式）
3) 仅保留指定年份（默认 2024）
4) 按 Section × 月份汇总计数，导出到 Excel
5) 在 Excel 中插入折线图（每条线一个 Section）

依赖：
    pip install pandas xlsxwriter

用法：
    python guardian_monthly_2024.py \
        --input theguardian_all_reformat \
        --output guardian_2024_monthly.xlsx \
        --year 2024
"""

from __future__ import annotations

import argparse
import logging
import re
from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Optional, Tuple, List

import pandas as pd


# ---- 配置区 ---------------------------------------------------------------

MONTH_ABBR = {
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "may": 5, "jun": 6,
    "jul": 7, "aug": 8, "sep": 9, "oct": 10, "nov": 11, "dec": 12,
}

# URL 中常见两种日期形式：
# 1) /2024/jan/31/
RE_DATE_ABBR = re.compile(r"/(?P<y>\d{4})/(?P<m>[a-z]{3})/(?P<d>\d{1,2})(?:/|$)")
# 2) /2024/01/31/
RE_DATE_NUM = re.compile(r"/(?P<y>\d{4})/(?P<m>\d{1,2})/(?P<d>\d{1,2})(?:/|$)")


@dataclass
class Config:
    input_dir: Path
    output_xlsx: Path
    year: int = 2024
    verbose: bool = False


# ---- 工具函数 -------------------------------------------------------------

def parse_url_date(url: str) -> Optional[date]:
    """
    从 Guardian 文章 URL 中解析日期。
    支持 /YYYY/mmm/DD 和 /YYYY/MM/DD 两种形式。
    解析失败返回 None。
    """
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
    读取单个 CSV，返回 DataFrame，仅保留必要列：
    ['Section', 'URL']，并附加解析出的 ['year', 'month']。
    自动识别分隔符（逗号/制表符）。
    """
    # sep=None + engine="python" 会自动猜测分隔符
    df = pd.read_csv(csv_path, sep=None, engine="python", dtype=str)
    # 统一列名到小写便于兼容
    df.columns = [c.strip().lower() for c in df.columns]

    # 最少需要 'section' 和 'url'
    required = {"section", "url"}
    missing = required - set(df.columns)
    if missing:
        raise ValueError(f"{csv_path} 缺少必要列: {missing}")

    # 仅保留关心的列
    df = df[["section", "url"]].copy()

    # 解析日期
    parsed = df["url"].map(parse_url_date)
    df["year"] = parsed.map(lambda d: d.year if d else None)
    df["month"] = parsed.map(lambda d: d.month if d else None)

    # 过滤掉未能解析日期的行
    df = df.dropna(subset=["year", "month"])
    df["year"] = df["year"].astype(int)
    df["month"] = df["month"].astype(int)
    return df


def build_pivot_monthly(df: pd.DataFrame, year: int) -> pd.DataFrame:
    """
    生成 Section × Month 的月度计数透视表，仅包含指定年份。
    列为 1..12，缺失填 0，并按 Section 排序。
    """
    dfy = df[df["year"] == year].copy()
    if dfy.empty:
        # 返回空表骨架，便于下游写 Excel
        return pd.DataFrame(columns=[f"{m:02d}" for m in range(1, 13)])

    # groupby 计数
    grp = (
        dfy.groupby(["section", "month"], dropna=False)
           .size()
           .rename("count")
           .reset_index()
    )

    # 透视：行=section，列=month
    pivot = grp.pivot(index="section", columns="month", values="count").fillna(0).astype(int)

    # 补齐 1..12 月
    for m in range(1, 13):
        if m not in pivot.columns:
            pivot[m] = 0

    # 列按月份排序，列名格式化为 01..12
    pivot = pivot.reindex(columns=sorted(pivot.columns))
    pivot.columns = [f"{m:02d}" for m in pivot.columns]

    # 行按 Section 字典序
    pivot = pivot.sort_index()
    return pivot


def write_excel_with_chart(pivot: pd.DataFrame, out_path: Path, year: int) -> None:
    """
    将透视表写入 Excel，并插入折线图：
    - Sheet1: Monthly_{year}  透视表
    - Sheet2: Chart_{year}    折线图（每条线一个 Section）
    """
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        # 写透视表
        sheet_data = f"Monthly_{year}"
        pivot.to_excel(writer, sheet_name=sheet_data)
        wb = writer.book
        ws_data = writer.sheets[sheet_data]

        # 美化表头、冻结窗格
        ws_data.freeze_panes(1, 1)
        ws_data.autofilter(0, 0, pivot.shape[0], pivot.shape[1])
        ws_data.set_column(0, 0, 24)   # Section 列宽
        ws_data.set_column(1, pivot.shape[1], 10)

        # 添加总计列（行合计），便于参考（不参与画图）
        start_row = 1  # DataFrame 写到 Excel 的起始数据行（含表头 = 0 行）
        start_col = 0  # Section 在 A 列
        n_rows = pivot.shape[0]
        n_cols = pivot.shape[1]

        total_col_letter = chr(ord('A') + 1 + n_cols)  # 合计列字母
        ws_data.write(0, 1 + n_cols, "Total")
        for i in range(n_rows):
            row_excel = start_row + i
            # B..(B+n_cols-1)
            first_cell = xl_cell(row_excel, 1)
            last_cell = xl_cell(row_excel, n_cols)
            ws_data.write_formula(row_excel, 1 + n_cols, f"=SUM({first_cell}:{last_cell})")

        # 新建图表工作表
        sheet_chart = f"Chart_{year}"
        ws_chart = wb.add_worksheet(sheet_chart)

        # 创建折线图
        chart = wb.add_chart({"type": "line"})
        chart.set_title({"name": f"Guardian {year} 每月数量（按 Section）"})
        chart.set_x_axis({"name": "月份 (01-12)"})
        chart.set_y_axis({"name": "数量"})
        chart.set_legend({"position": "bottom"})

        # X 轴分类（月份列）：取数据表第 1 行的月份标题
        # categories = =Monthly_year!$B$1:$M$1
        cat_first = xl_cell(0, 1)       # B1
        cat_last = xl_cell(0, n_cols)   # 对应到 M1
        categories_ref = f"='{sheet_data}'!${cat_first}:${cat_last}"

        # 为每个 Section 添加一条序列
        # 值区域：=Monthly_year!$B$r:$M$r  （r为具体数据行）
        for i in range(n_rows):
            row_excel = start_row + i
            series_name = f"='{sheet_data}'!${xl_cell(row_excel, 0)}"   # A{row}
            val_first = xl_cell(row_excel, 1)
            val_last = xl_cell(row_excel, n_cols)
            values_ref = f"='{sheet_data}'!${val_first}:${val_last}"
            chart.add_series({
                "name": series_name,
                "categories": categories_ref,
                "values": values_ref,
                # 不指定颜色，交由 Excel 默认调色
            })

        # 将图表插入图表工作表
        ws_chart.insert_chart("A1", chart, {"x_scale": 2.0, "y_scale": 1.6})


def xl_cell(row_zero_based: int, col_zero_based: int) -> str:
    """
    将 (0-based row, 0-based col) 转为 Excel 单元格标记，例如 (0,0)->A1, (0,1)->B1
    便于构造 XlsxWriter 的公式区域。
    """
    # 列号转字母
    col = col_zero_based
    letters: List[str] = []
    while True:
        col, rem = divmod(col, 26)
        letters.append(chr(ord('A') + rem))
        if col == 0:
            break
        col -= 1
    col_letters = "".join(reversed(letters))
    return f"{col_letters}{row_zero_based + 1}"


# ---- 主流程 ---------------------------------------------------------------

def run(cfg: Config) -> None:
    logging.info("扫描目录：%s", cfg.input_dir)

    csv_files = sorted(cfg.input_dir.rglob("guardian_*.csv"))
    if not csv_files:
        logging.warning("未找到任何 CSV：%s/guardian_*.csv", cfg.input_dir)
        # 仍然输出空 Excel（便于流水线不中断）
        empty = pd.DataFrame(columns=[f"{m:02d}" for m in range(1, 13)])
        write_excel_with_chart(empty, cfg.output_xlsx, cfg.year)
        logging.info("已写出空模板：%s", cfg.output_xlsx)
        return

    frames = []
    for p in csv_files:
        try:
            df = read_guardian_csv(p)
            frames.append(df)
            if cfg.verbose:
                logging.info("读取成功：%s（行数=%d）", p.name, len(df))
        except Exception as e:
            logging.error("读取失败：%s，原因：%s", p, e)

    if not frames:
        logging.warning("所有文件均未成功读取，输出空 Excel。")
        empty = pd.DataFrame(columns=[f"{m:02d}" for m in range(1, 13)])
        write_excel_with_chart(empty, cfg.output_xlsx, cfg.year)
        return

    all_df = pd.concat(frames, ignore_index=True)
    pivot = build_pivot_monthly(all_df, cfg.year)
    write_excel_with_chart(pivot, cfg.output_xlsx, cfg.year)

    logging.info("完成：%s  （Section×月份的月度汇总 + 折线图）", cfg.output_xlsx)


def parse_args() -> Config:
    ap = argparse.ArgumentParser(description="Guardian 月度统计（按 Section × 月份）")
    ap.add_argument("--input", "-i", type=Path, default=Path("theguardian_all_reformat"),
                    help="输入目录（递归查找 guardian_*.csv）")
    ap.add_argument("--output", "-o", type=Path, default=Path("guardian_2024_monthly.xlsx"),
                    help="输出 Excel 文件名")
    ap.add_argument("--year", "-y", type=int, default=2024,
                    help="统计年份（默认 2024）")
    ap.add_argument("--verbose", action="store_true", help="打印更详细的日志")
    args = ap.parse_args()
    return Config(
        input_dir=args.input,
        output_xlsx=args.output,
        year=args.year,
        verbose=args.verbose
    )


def main() -> None:
    cfg = parse_args()
    logging.basicConfig(
        level=logging.DEBUG if cfg.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s: %(message)s"
    )
    run(cfg)


if __name__ == "__main__":
    main()
