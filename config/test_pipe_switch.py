# -*- coding: utf-8 -*-
version = 1.0
name = '管道交换'
describe = '当前策略用于管道交换。'

modules = {
    'basic/replay': {},
    'basic/analyze': {},
    'basic/pipe_switch': {}
}

actions = [
    {'replay': {'pipe' : 1}},
    {'pipe_switch': {'action' : 'read', 'pipe' : 1}},
    {'pipe_switch': {'action' : 'write', 'pipe' : 2}},
    {'analyze': {'pipe' : 2}}
]
