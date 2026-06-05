"""Wiki 轻量查询：trk / chk / qry（飞书 Bot + CLI）。"""
from wiki.chk import run_chk
from wiki.qry import search_wiki
from wiki.trk import track_stock

__all__ = ["track_stock", "run_chk", "search_wiki"]
