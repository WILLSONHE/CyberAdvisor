"""用户持仓配置，供 fine_screen.py 等脚本读取。"""

HOLDERS = ["Wilson"]

HOLDINGS = [
    {"holder": "Wilson", "name": "上海电力", "code": "600021", "cost": 19.9102, "shares": 100, "price": 19.59, "market_value": 1959.0},
    {"holder": "Wilson", "name": "ST美丽", "code": "000010", "cost": 1.992, "shares": 2500, "price": 2.26, "market_value": 5650.0},
    {"holder": "Wilson", "name": "电光科技", "code": "002730", "cost": 34.7286, "shares": 300, "price": 29.69, "market_value": 8907.0},
]

CASH_BY_HOLDER = {
    "Wilson": 2.9
}

CASH_CNY = 2.9  # 全员 A 股现金合计（元）
