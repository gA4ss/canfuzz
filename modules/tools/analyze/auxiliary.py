# -*- coding: utf-8 -*-
import re
import ast
import time
import copy
import threading
import bitstring
import collections

from frame.kernel.module import CANModule, Command
from frame.message.can import CANMessage
from frame.message.uds import UDSMessage
from frame.message.isotp import ISOTPMessage
from frame.utils.frag import FragmentedCAN
from frame.utils.replay import Replay
from frame.utils.correl import SeparatedMessage
from frame.stream.subnet import Subnet
from frame.stream.separator import Separator
from frame.stream.cmdres import CmdResult, CMDRES_ERROR, CMDRES_NULL, CMDRES_INT, CMDRES_STR, CMDRES_TAB, CMDRES_OBJ

def do_clean(self):
  self.all_frames = [{'name': 'start_buffer', 'buf': Replay()}]
  self.dump_stat = Replay()
  self._train_buffer = -1
  self._index = 0
  self.data_set = {}
  self.commands['test'].is_enabled = False
  self.commands['dumps'].is_enabled = False
  return CmdResult(cmdline='clean', describe="清空所有缓存区")

def do_add_meta_descr_data(self, input_params):
  try:
    fid, body, descr = input_params.split(',')
    num_fid = int(fid.strip(), 0)
    if 'description' not in self.meta_data:
      self.meta_data['description'] = {}
    self.meta_data['description'][(num_fid, body.strip().upper())] = descr.strip()
    return CmdResult(cmdline='note ' + input_params, describe="描述数据被添加")
  except Exception as e:
    return CmdResult(cmdline='note ' + input_params, describe="添加元数据数据描述错误", last_error=-2, e=e)

def do_add_meta_bit_data(self, input_params):
  """
  增加元数据
  元数据以CANID+LENGTH作为索引。
  CANID,LENGTH,<UDS|FRAG|ISO>:<位索引>:<描述>[,...]
  """
  try:
    # 取出CANID与数据长度
    fid, leng = input_params.split(',')[0:2]
    descr = input_params.split(',')[2:]         # 以','分割每位的描述
    num_fid = int(fid.strip(), 0)
    if 'bits' not in self.meta_data:
      self.meta_data['bits'] = {}
    bitsX = []
    # <UDS|FRAG|ISO>:<最后一位索引>:<描述>
    for dsc in descr:
      # 第一个区域是数据类型
      # 第二个区域是位索引
      # 第三个区域是描述
      bitsX.append({dsc.split(":")[0].strip(): {int(dsc.split(":")[1]): dsc.split(":")[2].strip()}})
    # 在元数据上添加一条
    self.meta_data['bits'][(num_fid, int(leng))] = bitsX
    return CmdResult(cmdline='note2 ' + input_params, describe="字段数据已经被添加")
  except Exception as e:
    return CmdResult(cmdline='note2 ' + input_params, describe="添加元数据位描述错误", last_error=-2, e=e)

def do_load_meta(self, filename):
  """
  加载元文件'meta file'
  """
  try:
    data = ""
    with open(filename.strip(), "r") as ins:
      for line in ins:
        data += line
    self.meta_data = ast.literal_eval(data)
  except Exception as e:
    return CmdResult(cmdline='lnote ' + filename, describe="不能加载元数据文件", last_error=-2, e=e)
  return CmdResult(cmdline='lnote ' + filename, describe="已加载元数据文件", result_type=CMDRES_STR, result=filename)

def do_save_meta(self, filename):
  try:
    _file = open(filename.strip(), 'w')
    _file.write(str(self.meta_data))
    _file.close()
  except Exception as e:
    return CmdResult(cmdline='snote ' + filename, describe="不能保存元数据文件", last_error=-2, e=e)
  return CmdResult(cmdline='snote ' + filename, describe="保存元数据文件", result_type=CMDRES_STR, result=filename)

def get_delay(self, speed):
  """
  获取'ping/fuzz'的延迟值 (实验)
  g speed

  speed: 总线速率(Kb/s)
  """
  _speed = float(speed) * 1024
  curr_1 = len(self.all_frames[self._index]['buf'])
  time.sleep(3)
  curr_2 = len(self.all_frames[self._index]['buf'])

  # 这里是两个缓冲区的长度相减法，数据包的长度差异
  diff = curr_2 - curr_1
  speed = int((diff * 80) / 3)
  # 计算延迟
  delay = 1 / int((_speed - speed) / 80)
  delay_str = '{} (KB/s)'.format(delay)
  return CmdResult(cmdline='delay ' + str(speed), describe="平均延迟", result_type=CMDRES_STR, result=delay_str)