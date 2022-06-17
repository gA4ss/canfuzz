version = 1.0
name = '设备探索测试'
describe = '当前策略用于车辆未知设备的探索。'

modules = {
    'io/hw_edeck': {'bus_num': 0, 'bus_speed': 500},
    'tools/analyze': {},
    'tools/ping': {}
}

actions = [
    {'hw_edeck': {'action': 'read', 'pipe': 2}},
    {'analyze': {'pipe': 2}},
    {'ping': {
        'pipe': 1,
        'delay': 0.06,
        'body': '0301000000000000',
        'range': [0x130, 0x140],
        'mode': 'CAN'}
    },
    {'hw_edeck': {'action': 'write', 'pipe': 1}}
]