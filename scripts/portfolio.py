"""用户持仓配置，供 fine_screen.py 等脚本读取。"""

HOLDERS = ["Wilson", "刘岚", "微"]

HOLDINGS = [
    {"holder": "Wilson", "name": "上海电力", "code": "600021", "cost": 18.7602, "shares": 200, "price": 17.27, "market_value": 3454.0},
    {"holder": "Wilson", "name": "ST美丽", "code": "000010", "cost": 1.992, "shares": 2500, "price": 2.31, "market_value": 5775.0},
    {"holder": "Wilson", "name": "电光科技", "code": "002730", "cost": 34.7286, "shares": 300, "price": 28.31, "market_value": 8493.0},
    {"holder": "刘岚", "name": "旗天科技", "code": "300061", "cost": 16.9432, "shares": 1300, "price": 7.93, "market_value": 10309.0},
    {"holder": "刘岚", "name": "国民技术", "code": "02701", "cost": 13.3311, "shares": 20000, "price": 11.1, "market_value": 222000.0},
    {"holder": "刘岚", "name": "高乐股份", "code": "002348", "cost": 172.9754, "shares": 200, "price": 12.12, "market_value": 2424.0},
    {"holder": "刘岚", "name": "章源钨业", "code": "002378", "cost": -1100.7596, "shares": 500, "price": 30.57, "market_value": 15285.0},
    {"holder": "刘岚", "name": "金力永磁", "code": "300748", "cost": 38.4885, "shares": 500, "price": 29.41, "market_value": 14705.0},
    {"holder": "刘岚", "name": "国科微", "code": "300672", "cost": 315.0318, "shares": 1000, "price": 274.49, "market_value": 274490.0},
    {"holder": "刘岚", "name": "恒生电子", "code": "600570", "cost": 49.1354, "shares": 1000},
    {"holder": "刘岚", "name": "陕西华达", "code": "301517", "cost": 63.8958, "shares": 15000, "price": 52.11, "market_value": 781650.0},
    {"holder": "刘岚", "name": "胜宏科技", "code": "300476", "cost": 292.932, "shares": 100, "price": 330.26, "market_value": 33026.0},
    {"holder": "微", "name": "天汽模", "code": "002510", "cost": 6.88, "shares": 500, "price": 6.54, "market_value": 3270.0},
    {"holder": "微", "name": "贝因美", "code": "002570", "cost": 5.25, "shares": 500, "price": 5.16, "market_value": 2580.0},
    {"holder": "微", "name": "山西焦煤", "code": "000983", "cost": 7.3, "shares": 500, "price": 7.17, "market_value": 3585.0},
]

CASH_BY_HOLDER = {
    "Wilson": 350.7,
    "刘岚": 514997.0
}

CASH_CNY = 515347.7  # 全员 A 股现金合计（元）
