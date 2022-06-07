# -*- coding: utf-8 -*-
version = 1.0
name = '回访缓存测试'
describe = '当前策略用于回访模式测试'

modules = {
  #'io/hw_edeck': {'bus_num': 0, 'bus_speed': 500},
  'tools/sniffer': {'load_from' : 'E:\\workspace\\vehiclepwn\\canfuzz\\dumps\\x.dump'}
}

actions = [
  {'sniffer': {'pipe' : 1}}
]
