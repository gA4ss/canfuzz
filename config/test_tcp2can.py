# -*- coding: utf-8 -*-
version = 1.0
name = 'TCP2CAN测试'
describe = '当前策略用于TCP2CAN模式测试,这里将TCP2CAN~1与TCP2CAN~2进行链接'

modules = {
    'io/hw_TCP2CAN~1': {'mode': 'server', 'port': 1111, 'address': '127.0.0.1'},
    'io/hw_TCP2CAN~2': {'mode': 'client', 'port': 1111, 'address': '127.0.0.1'},
    'tools/analyze': {},
}

actions = [
    {'hw_TCP2CAN~1': {'pipe' : 1}},     # 从tcp1接收CAN数据
    {'analyze': {'action' : 'read', 'pipe' : 1}},
    {'hw_TCP2CAN~2': {'pipe' : 2}}      # 从tcp2发出CAN数据
]
