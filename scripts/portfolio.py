"""用户持仓配置，供 fine_screen.py 等脚本读取。"""

HOLDERS = ["Wilson", "刘岚", "微"]

HOLDINGS = [
    {"holder": "Wilson", "name": "上海电力", "code": "600021", "cost": 18.7602, "shares": 200, "price": 17.41, "market_value": 3482.0},
    {"holder": "Wilson", "name": "ST美丽", "code": "000010", "cost": 1.992, "shares": 2500, "price": 2.31, "market_value": 5775.0},
    {"holder": "Wilson", "name": "电光科技", "code": "002730", "cost": 34.7286, "shares": 300, "price": 28.24, "market_value": 8472.0},
    {"holder": "刘岚", "name": "旗天科技", "code": "300061", "cost": 16.9432, "shares": 1300, "price": 7.82, "market_value": 10166.0},
    {"holder": "刘岚", "name": "国民技术", "code": "02701", "cost": 13.3311, "shares": 20000, "price": 11.12, "market_value": 222400.0},
    {"holder": "刘岚", "name": "高乐股份", "code": "002348", "cost": 172.9754, "shares": 200},
    {"holder": "刘岚", "name": "章源钨业", "code": "002378", "cost": -1100.7596, "shares": 500, "price": 30.06, "market_value": 15030.0},
    {"holder": "刘岚", "name": "金力永磁", "code": "300748", "cost": 38.4885, "shares": 500, "price": 29.52, "market_value": 14760.0},
    {"holder": "刘岚", "name": "国科微", "code": "300672", "cost": 315.0318, "shares": 1000, "price": 275.28, "market_value": 275280.0},
    {"holder": "刘岚", "name": "恒生电子", "code": "600570", "cost": 49.1354, "shares": 1000, "price": 21.82, "market_value": 21820.0},
    {"holder": "刘岚", "name": "陕西华达", "code": "301517", "cost": 63.8958, "shares": 15000, "price": 52.08, "market_value": 781200.0},
    {"holder": "刘岚", "name": "胜宏科技", "code": "300476", "cost": 292.932, "shares": 100, "price": 330.75, "market_value": 33075.0},
    {"holder": "微", "name": "天汽模", "code": "002510", "cost": 6.88, "shares": 500, "price": 6.67, "market_value": 3335.0},
    {"holder": "微", "name": "贝因美", "code": "002570", "cost": 5.25, "shares": 500, "price": 5.21, "market_value": 2605.0},
    {"holder": "微", "name": "山西焦煤", "code": "000983", "cost": 7.3, "shares": 500, "price": 7.23, "market_value": 3615.0},
]

CASH_BY_HOLDER = {
    "Wilson": 2111.72,
    "刘岚": 514997.0
}

CASH_CNY = 517108.72  # 全员 A 股现金合计（元）
