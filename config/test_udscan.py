# -*- coding: utf-8 -*-
version = "1.0"
name = "UDS扫描"
describe = "当前策略用于通过硬件设备读取CAN数据包并进行UDS扫描。"

modules = {
    'io/hw_edeck': {'bus_speed': 500}, 
    'tools/ping': {}, 
    'tools/analyze': {}
}

actions = [
    {'hw_edeck': {'action': 'read', 'pipe': '1'}}, 
    {'analyze': {}},
    {'ping': {
        'pipe': '2', 
        'delay': '0.06', 
        'range': [0x100, 0x140], 
        'services': [{"service":16,"sub":1}, {"service":62,"sub":1}], 
        'mode': 'UDS'}
    }, 
    {'analyze': {'pipe': '2'}}, 
    {'hw_edeck': {'action': 'write', 'pipe': '2'}}
]
