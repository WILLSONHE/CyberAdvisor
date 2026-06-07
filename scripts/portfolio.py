"""用户持仓配置，供 fine_screen.py 等脚本读取。"""

HOLDERS = ["Wilson", "刘岚"]

HOLDINGS = [
    {"holder": "Wilson", "name": "上海电力", "code": "600021", "cost": 19.9102, "shares": 100, "price": 19.4, "market_value": 1940.0},
    {"holder": "Wilson", "name": "ST美丽", "code": "00010", "cost": 1.992, "shares": 2500, "price": 14.23, "market_value": 35575.0},
    {"holder": "Wilson", "name": "电光科技", "code": "02730", "cost": 34.7286, "shares": 300},
    {"holder": "刘岚", "name": "旗天科技", "code": "300061", "cost": 16.9432, "shares": 1300, "price": 8.98, "market_value": 11674.0},
    {"holder": "刘岚", "name": "国民技术", "code": "02701", "cost": 13.3311, "shares": 20000, "price": 11.92, "market_value": 238400.0},
    {"holder": "刘岚", "name": "高乐股份", "code": "02348", "cost": 172.9754, "shares": 200, "price": 1.07, "market_value": 214.0},
    {"holder": "刘岚", "name": "章源钨业", "code": "02378", "cost": -1100.7596, "shares": 500, "price": 101.1, "market_value": 50550.0},
    {"holder": "刘岚", "name": "金力永磁", "code": "300748", "cost": 38.4885, "shares": 500, "price": 31.12, "market_value": 15560.0},
    {"holder": "刘岚", "name": "国科微", "code": "300672", "cost": 315.0318, "shares": 1000, "price": 299.0, "market_value": 299000.0},
    {"holder": "刘岚", "name": "恒生电子", "code": "600570", "cost": 49.1354, "shares": 1000},
    {"holder": "刘岚", "name": "陕西华达", "code": "301517", "cost": 63.8958, "shares": 15000, "price": 55.65, "market_value": 834750.0},
    {"holder": "刘岚", "name": "胜宏科技", "code": "300476", "cost": 292.932, "shares": 100, "price": 338.9, "market_value": 33890.0},
]

CASH_BY_HOLDER = {
    "Wilson": 2111.72,
    "刘岚": 514997.0
}

CASH_CNY = 517108.72  # 全员 A 股现金合计（元）
