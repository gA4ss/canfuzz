# -*- coding: utf-8 -*-
version = 1.0
name = '真实FUZZ引擎测试'
describe = '用于真实环境下的FUZZ测试'

modules = {
    'io/hw_edeck': {'bus_num': 0, 'bus_speed': 500, 'active': False},
    'tools/fuzz': {},
    'tools/analyze': {},
}

actions = [
    {'fuzz': { 
        'id': [0x131, 0x132],               # CANID列表
        # 基础数据
        'data': [0, 0, 0, 1, 0, 0, 0, 0],
        'index': [0, 1, 5, 7],
        'bytes': [1, 2, 3, 4, 0],           # 如果是一个双元组则是一个范围
        'delay': 0.07, 
        'pipe': 1 }
    },
    {'analyze': {'action': 'read', 'pipe' : 1}},
    {'hw_edeck': {'action': 'write', 'pipe' : 1}}
]
