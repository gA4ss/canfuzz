# -*- coding: utf-8 -*-
from frame.kernel.module import CANModule


class filter(CANModule):
  name = "CAN过滤器"
  help = {
    "describe": "此模块用于过滤指定得CAN数据包。",
    "action_parameters": {
      "black_list": {
        "describe": "当前CANID在黑名单中,进行阻断。",
        "type": "list,int"
      },
      "white_list": {
        "describe": "当前CANID不在白名单中，进行阻断。",
        "type": "list,int"
      },
      "white_body": {
        "describe": "对CAN数据进行审核，如果不在白名单中则阻断，其值是一个整数列表。",
        "type": "list,int"
      },
      "black_body": {
        "describe": "对CAN数据进行审核，如果在黑名单中则阻断，其值是一个整数列表。",
        "type": "list,int"
      },
      "hex_white_body": {
        "describe": "对CAN数据进行审核，如果不在白名单中则阻断，描述数据使用16进制字符串。",
        "type": "list,int"
      },
      "hex_black_body": {
        "describe": "对CAN数据进行审核，如果在黑名单中则阻断，描述数据使用16进制字符串。",
        "type": "list,int"
      },
      "black_bus": {
        "describe": "如果bus是在黑名单的，则阻断。",
        "type": "list,int"
      },
      "white_bus": {
        "describe": "如果bus是不在白名单的，则阻断。",
        "type": "list,int"
      }
    }
  }

  version = 1.0

  def do_init(self, params):
    self.describe = filter.help.get('describe', filter.name)
    self._bus = 'filter'

  def do_effect(self, can_msg, args):
    if can_msg.CANData:
      # 当前CANID不在白名单中,将CANData设置为False进行阻断
      if 'white_list' in args and can_msg.CANFrame.frame_id not in args.get('white_list', []):
        can_msg.CANData = False
        self.info("数据帧 " + str(can_msg.CANFrame.frame_id) + " 被拦截(BL) (BUS = " + str(
          can_msg.bus) + ")")
      # 当前CANID在黑名单中，将CANData设置为False进行阻断
      elif 'black_list' in args and can_msg.CANFrame.frame_id in args.get('black_list', []):
        can_msg.CANData = False
        self.info("数据帧 " + str(can_msg.CANFrame.frame_id) + " 被拦截(WL) (BUS = " + str(
          can_msg.bus) + ")")
      # 对CAN数据进行审核，如果不在白名单中则阻断，其值是一个整数列表
      if 'white_body' in args and can_msg.CANFrame.frame_data not in args.get('white_body', []):
        can_msg.CANData = False
        self.info("数据帧 " + str(can_msg.CANFrame.frame_id) + " 被拦截(WB) (BUS = " + str(
          can_msg.bus) + ")")
      # 对CAN数据进行审核，如果在黑名单中则阻断，其值是一个整数列表
      elif 'black_body' in args and can_msg.CANFrame.frame_data in args.get('black_body', []):
        can_msg.CANData = False
        self.info("数据帧 " + str(can_msg.CANFrame.frame_id) + " 被拦截(BB) (BUS = " + str(
          can_msg.bus) + ")")
      # 对CAN数据进行审核，如果不在白名单中则阻断，描述数据使用16进制字符串
      if 'hex_white_body' in args and self.get_hex(can_msg.CANFrame.frame_raw_data) not in args.get('hex_white_body', []):
        can_msg.CANData = False
        self.info("数据帧 " + str(can_msg.CANFrame.frame_id) + " 被拦截(WB) (BUS = " + str(
          can_msg.bus) + ")")
      # 对CAN数据进行审核，如果在黑名单中则阻断，描述数据使用16进制字符串
      elif 'hex_black_body' in args and self.get_hex(can_msg.CANFrame.frame_raw_data) in args.get('hex_black_body', []):
        can_msg.CANData = False
        self.info("数据帧 " + str(can_msg.CANFrame.frame_id) + " 被拦截(BB) (BUS = " + str(
          can_msg.bus) + ")")
      # 如果bus是在黑名单的，则阻断
      if 'black_bus' in args and can_msg.bus.strip() in args.get('black_body', []):
        can_msg.CANData = False
        self.info("数据帧 " + str(can_msg.CANFrame.frame_id) + " 被拦截(BBus) (BUS = " + str(
          can_msg.bus) + ")")
      # 如果bus是不在白名单的，则阻断
      elif 'white_bus' in args and can_msg.bus.strip() not in args.get('white_bus', []):
        can_msg.CANData = False
        self.info("数据帧 " + str(can_msg.CANFrame.frame_id) + " 被拦截(WBus) (BUS = " + str(
          can_msg.bus) + ")")
    return can_msg
