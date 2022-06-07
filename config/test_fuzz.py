# -*- coding: utf-8 -*-
version = 1.0
name = 'FUZZ引擎测试'
describe = '当前策略用于FUZZ引擎测试。'

modules = {
    'basic/fuzz': {},
    'basic/analyze': {},
}

actions = [
    {'fuzz': { 
        'id': [0x131, 0x132],               # CANID列表
        # 基础数据
        'data': [0, 0, 0, 1, 0, 0, 0, 0],
        'index': [0, 1],
        'bytes': [1, 2, 3, 4, 0],           # 如果是一个双元组则是一个范围
        'delay': 0.07, 
        'pipe': 1 }
    },
    {'analyze': {'pipe' : 1}}
]
