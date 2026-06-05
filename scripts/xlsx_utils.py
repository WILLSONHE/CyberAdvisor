"""Excel 写入与数字显示格式（千位分隔）。"""
from __future__ import annotations

from openpyxl import load_workbook

MONEY_FMT = "#,##0.00"
INT_FMT = "#,##0"

PORTFOLIO_MONEY_COLS = ("成本",)
PORTFOLIO_INT_COLS = ("股数",)

SIM_MONEY_COLS = ("成本", "现价", "市值", "盈亏")
SIM_INT_COLS = ("股数", "持仓时间(天)")


def apply_column_formats(
    path: str,
    *,
    money_cols: tuple[str, ...] = (),
    int_cols: tuple[str, ...] = (),
    sheet: str | None = None,
) -> None:
    """为已存在的 xlsx 设置列数字格式（不改变单元格数值）。"""
    wb = load_workbook(path)
    ws = wb[sheet or wb.sheetnames[0]]
    headers = [cell.value for cell in ws[1]]
    col_idx = {str(h).strip(): i + 1 for i, h in enumerate(headers) if h is not None}

    for col_name in money_cols:
        ci = col_idx.get(col_name)
        if not ci:
            continue
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=ci)
            if isinstance(cell.value, (int, float)):
                cell.number_format = MONEY_FMT

    for col_name in int_cols:
        ci = col_idx.get(col_name)
        if not ci:
            continue
        for row in range(2, ws.max_row + 1):
            cell = ws.cell(row=row, column=ci)
            if isinstance(cell.value, (int, float)) and not isinstance(cell.value, bool):
                cell.number_format = INT_FMT

    wb.save(path)


def write_dataframe_xlsx(
    df,
    path: str,
    *,
    money_cols: tuple[str, ...] = (),
    int_cols: tuple[str, ...] = (),
) -> None:
    df.to_excel(path, index=False)
    apply_column_formats(path, money_cols=money_cols, int_cols=int_cols)


def format_portfolio_xlsx(path: str) -> None:
    apply_column_formats(path, money_cols=PORTFOLIO_MONEY_COLS, int_cols=PORTFOLIO_INT_COLS)


def format_sim_xlsx(path: str) -> None:
    apply_column_formats(path, money_cols=SIM_MONEY_COLS, int_cols=SIM_INT_COLS)
