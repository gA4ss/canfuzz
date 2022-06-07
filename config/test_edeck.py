# -*- coding: utf-8 -*-
version = 1.0
name = 'edeck缓存测试'
describe = '当前策略用于edeck测试'

modules = {
    'io/hw_edeck': {'bus_num': 0, 'bus_speed': 500},
    'basic/analyze': {}
}

actions = [
    {'hw_edeck': {'action': 'read', 'pipe': 1}},
    {'analyze': {'action': 'read', 'pipe' : 1}},
    {'analyze': {'action': 'write', 'pipe' : 2}},
    {'hw_edeck': {'action': 'write', 'pipe': 2}}
]
