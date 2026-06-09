"""用户持仓配置，供 fine_screen.py 等脚本读取。"""

HOLDERS = ["Wilson", "刘岚", "微"]

HOLDINGS = [
    {"holder": "Wilson", "name": "上海电力", "code": "600021", "cost": 19.9102, "shares": 100, "price": 18.22, "market_value": 1822.0},
    {"holder": "Wilson", "name": "ST美丽", "code": "000010", "cost": 1.992, "shares": 2500, "price": 2.43, "market_value": 6075.0},
    {"holder": "Wilson", "name": "电光科技", "code": "002730", "cost": 34.7286, "shares": 300, "price": 28.52, "market_value": 8556.0},
    {"holder": "刘岚", "name": "旗天科技", "code": "300061", "cost": 16.9432, "shares": 1300, "price": 8.16, "market_value": 10608.0},
    {"holder": "刘岚", "name": "国民技术", "code": "02701", "cost": 13.3311, "shares": 20000, "price": 11.74, "market_value": 234800.0},
    {"holder": "刘岚", "name": "高乐股份", "code": "002348", "cost": 172.9754, "shares": 200, "price": 12.76, "market_value": 2552.0},
    {"holder": "刘岚", "name": "章源钨业", "code": "002378", "cost": -1100.7596, "shares": 500, "price": 30.41, "market_value": 15205.0},
    {"holder": "刘岚", "name": "金力永磁", "code": "300748", "cost": 38.4885, "shares": 500, "price": 30.09, "market_value": 15045.0},
    {"holder": "刘岚", "name": "国科微", "code": "300672", "cost": 315.0318, "shares": 1000, "price": 283.65, "market_value": 283650.0},
    {"holder": "刘岚", "name": "恒生电子", "code": "600570", "cost": 49.1354, "shares": 1000, "price": 22.27, "market_value": 22270.0},
    {"holder": "刘岚", "name": "陕西华达", "code": "301517", "cost": 63.8958, "shares": 15000, "price": 53.91, "market_value": 808650.0},
    {"holder": "刘岚", "name": "胜宏科技", "code": "300476", "cost": 292.932, "shares": 100, "price": 342.55, "market_value": 34255.0},
    {"holder": "微", "name": "天汽模", "code": "002510", "cost": 6.88, "shares": 500, "price": 6.77, "market_value": 3385.0},
    {"holder": "微", "name": "贝因美", "code": "002570", "cost": 5.25, "shares": 500, "price": 5.36, "market_value": 2680.0},
    {"holder": "微", "name": "山西焦煤", "code": "000983", "cost": 7.3, "shares": 500, "price": 7.46, "market_value": 3730.0},
]

CASH_BY_HOLDER = {
    "Wilson": 2111.72,
    "刘岚": 514997.0
}

CASH_CNY = 517108.72  # 全员 A 股现金合计（元）
