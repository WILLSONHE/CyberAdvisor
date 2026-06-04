#!/usr/bin/env python3
"""飞书 Webhook 推送入口（可从项目根目录调用）。"""
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from feishu.notify import main

if __name__ == "__main__":
    main()
