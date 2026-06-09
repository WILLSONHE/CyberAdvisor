"""用户持仓配置，供 fine_screen.py 等脚本读取。"""

HOLDERS = ["Wilson", "刘岚"]

HOLDINGS = [
    {"holder": "Wilson", "name": "上海电力", "code": "600021", "cost": 19.9102, "shares": 100, "price": 17.71, "market_value": 1771.0},
    {"holder": "Wilson", "name": "ST美丽", "code": "000010", "cost": 1.992, "shares": 2500, "price": 2.31, "market_value": 5775.0},
    {"holder": "Wilson", "name": "电光科技", "code": "002730", "cost": 34.7286, "shares": 300, "price": 27.79, "market_value": 8337.0},
    {"holder": "刘岚", "name": "旗天科技", "code": "300061", "cost": 16.9432, "shares": 1300, "price": 8.15, "market_value": 10595.0},
    {"holder": "刘岚", "name": "国民技术", "code": "02701", "cost": 13.3311, "shares": 20000, "price": 11.02, "market_value": 220400.0},
    {"holder": "刘岚", "name": "高乐股份", "code": "002348", "cost": 172.9754, "shares": 200, "price": 12.9, "market_value": 2580.0},
    {"holder": "刘岚", "name": "章源钨业", "code": "002378", "cost": -1100.7596, "shares": 500, "price": 30.1, "market_value": 15050.0},
    {"holder": "刘岚", "name": "金力永磁", "code": "300748", "cost": 38.4885, "shares": 500, "price": 29.19, "market_value": 14595.0},
    {"holder": "刘岚", "name": "国科微", "code": "300672", "cost": 315.0318, "shares": 1000, "price": 276.7, "market_value": 276700.0},
    {"holder": "刘岚", "name": "恒生电子", "code": "600570", "cost": 49.1354, "shares": 1000, "price": 22.26, "market_value": 22260.0},
    {"holder": "刘岚", "name": "陕西华达", "code": "301517", "cost": 63.8958, "shares": 15000, "price": 52.85, "market_value": 792750.0},
    {"holder": "刘岚", "name": "胜宏科技", "code": "300476", "cost": 292.932, "shares": 100, "price": 314.8, "market_value": 31480.0},
]

CASH_BY_HOLDER = {
    "Wilson": 2111.72,
    "刘岚": 514997.0
}

CASH_CNY = 517108.72  # 全员 A 股现金合计（元）
