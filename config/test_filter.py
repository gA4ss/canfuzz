# -*- coding: utf-8 -*-
version = 1.0
name = '过滤器测试'
describe = '当前策略用于测试过滤器。'

modules = {
    'tools/analyze~1': {},
    'tools/analyze~2': {},
    'tools/sniffer~1': {'bus': 'sniffer1'},
    'tools/sniffer~2': {'bus': 'sniffer2'},
    'tools/filter': {},
}

actions = [
    {'sniffer~1': {'pipe': 1}},
    {'sniffer~2': {'pipe': 2}},
    {'filter': {'pipe': 1, 'white_bus': ["sniffer1"]}},
    {'filter': {'pipe': 2, 'white_bus': ["sniffer1"]}},
    {'analyze~1': {'pipe': 1}},
    {'analyze~2': {'pipe': 2}}
]
