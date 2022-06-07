# -*- coding: utf-8 -*-
version = 1.0
name = '过滤器测试'
describe = '当前策略用于测试过滤器。'

modules = {
    'basic/analyze~1': {},
    'basic/analyze~2': {},
    'basic/replay~1': {'bus': 'replay1'},
    'basic/replay~2': {'bus': 'replay2'},
    'basic/filter': {},
}

actions = [
    {'replay~1': {'pipe' : 1}},
    {'replay~2': {'pipe' : 2}},
    {'filter': {'pipe' : 1, 'white_bus': ["replay1"]}},
    {'filter': {'pipe' : 2, 'white_bus': ["replay1"]}},
    {'analyze~1': {'pipe' : 1}},
    {'analyze~2': {'pipe' : 2}}
]
