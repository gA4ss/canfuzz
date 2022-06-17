# -*- coding: utf-8 -*-
version = 1.0
name = '管道交换'
describe = '当前策略用于管道交换。'

modules = {
    'tools/sniffer': {},
    'tools/analyze': {},
    'tools/pipe_switch': {}
}

actions = [
    {'sniffer': {'pipe' : 1}},
    {'pipe_switch': {'action' : 'read', 'pipe' : 1}},
    {'pipe_switch': {'action' : 'write', 'pipe' : 2}},
    {'analyze': {'pipe' : 2}}
]
