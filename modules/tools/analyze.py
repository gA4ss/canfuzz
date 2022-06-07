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


class analyze(CANModule):
  name = "分析引擎"
  version = 1.0  # 版本
  help = {
    "describe": "此模块的主要功能是对CAN协议包提供统计分析功能，并将结果输出到屏幕或者文件。以及提供对新的CAN设备的探索与发现。",
    "init_parameters": {
      "uds_shift": {
        "describe": "UDS协议偏移量。",
        "type": "int",
        "default": 8,
        "range": [1, 2, 3, 4, 5, 6, 7, 8]
      },
      "meta_file": {
        "describe": "元数据文件路径。",
        "type": "str",
        "default": "./dump.meta"
      }
    },
    "action_parameters": {
      "action": {
        "describe": "动作属性，读或者写。",
        "type": "str",
        "default": "read",
        "range": ["read", "write"]
      }
    }
  }

  def do_init(self, params):
    """
    分析引擎初始化操作
    """
    self.describe = analyze.help.get('describe', analyze.name)
    self._bus = 'analyze'
    self.ISOList = None              # ISOTP协议列表
    self.UDSList = None              # UDS设备列表

    self._bodyList = None            # 缓冲区列表
    self._logFile = False            # 是否产生日志文件

    #
    # all_frames中保存了所有数据帧是一个字典形式
    #
    self.all_frames = [{'name': 'start_buffer', 'buf': Replay()}]
    self.dump_stat = Replay()
    self._index = 0
    self._rep_index = None

    #
    # meta_data 是元数据的保存字典
    # 'bits' : { (CANID，长度) : <UDS|FRAG|ISO>:位索引:描述, ... }
    # 'description' : { (CANID, 消息内容) : 描述内容, ... }
    #
    self.meta_data = {}
    self._bodyList = collections.OrderedDict()

    # UDS协议偏移
    self.shift = params.get('uds_shift', 8)
    self.subnet = Subnet(lambda stream: Separator(SeparatedMessage.builder))
    self.data_set = {}
    self._train_buffer = -1

    #
    # 线程安全事件设置
    #
    self._action = threading.Event()
    self._action.clear()

    self._last = 0
    self._full = 1
    self._need_status = False
    self._stat_resend = None
    self._active_check = False

    # 如果'meta_file'在参数中，则加载元文件
    if 'meta_file' in params:
        ret = self.do_load_meta(params['meta_file'])
        if ret.last_error < 0:
            self.error(ret.describe, ret.e)

    #
    # 常规手工分析
    #
    self.commands['print'] = Command("以表格形式打印缓冲区内容", 1, "[缓冲区索引]", self.do_print, True)
    self.commands['protocol'] = Command("分析捕获的数据包协议", 1, "<UDS|ISO|FRAG|ALL(默认)>,[缓冲区索引]", self.do_anal, True)
    self.commands['uds'] = Command("    - UDS偏移值", 1, "[偏移值]", self.change_shift, True)
    self.commands['newbuf'] = Command("新建一个缓冲区", 1, "[缓冲区名称]", self.new_diff, True)
    self.commands['diff'] = Command("打印两个缓冲区之间的不同", 1, "[缓冲区1的索引], [缓冲区2的索引], [对比数据的最大范围(字节)，默认:2048字节]", self.print_diff, True)
    self.commands['diff2'] = Command("打印两个缓冲区之间的不同,忽略内容", 1, "[缓冲区1的索引], [缓冲区2的索引]", self.print_diff_id, True)
    self.commands['rdiff'] = Command("对比两个缓冲区之间的不同,将不同保存到回放文件中(类似'diff'命令)", 1, "<文件名>, [缓冲区1的索引], [缓冲区2的索引], [对比数据的最大范围(字节)，默认:2048字节]", self.print_dump_diff, True)
    self.commands['rdiff2'] = Command("对比两个缓冲区之间的不同,将不同保存到回放文件中(类似'diff2'命令)，忽略内容", 1, "<文件名>, [缓冲区1的索引], [缓冲区2的索引]", self.print_dump_diff_id, True)
    self.commands['search'] = Command("在所有的缓冲区中找寻指定CANID的数据包", 1, "<CANID>", self.search_id, True)
    
    #
    # ECU探测相关
    #
    self.commands['change'] = Command("探测ECU的改变 (测试)", 1, "[缓冲区的索引], [最大发生改变的次数]", self.show_change, True)
    self.commands['detect'] = Command("通过控制帧探测ECU的改变 (测试)", 1, "<CANID:十六进制数据>[,缓冲区索引]", self.show_detect, True)
    self.commands['show'] = Command("显示所有已经检测ECU的变量 (测试)", 1, "[缓冲区索引]", self.show_fields, True)
    self.commands['fields'] = Command("显示选中ECU的所有变量 (测试)", 1, "<CANID>[, bin|hex|int|ascii [, 缓冲区索引]]", self.show_fields_ecu, True)
    
    #
    # 统计自动分析
    #
    self.commands['statistic'] = Command("堆栈检查: 在当前流量中进行分析 (统计)", 1, "[缓冲区索引]", self.train, True)
    self.commands['hypothesis'] = Command("堆栈检查: 在当前流量中通过已经学习到的知识，来寻找差异包 (统计)", 1, "[缓冲区索引]", self.find_ab, True)
    self.commands['test'] = Command("堆栈检查: 在当前流量中找寻动作 (统计)", 0, "", self.act_detect, False)
    self.commands['dumps'] = Command("堆栈检查: 在当前流量中探索异常包并保存到回访文件 (统计)", 1, "<文件名>", self.dump_ab, False)
    #
    # 辅助功能
    #
    self.commands['clean'] = Command("清除所有表与缓冲区", 0, "", self.do_clean, True)
    self.commands['note'] = Command("元数据: 对一帧添加描述", 1, "<CANID>, <十六进制的字符串>, <描述>", self.do_add_meta_descr_data, True)
    self.commands['note2'] = Command("元数据: 位域描述", 1, "<CANID>, <长度>, <类型>:<位索引>:<描述>[,...]", self.do_add_meta_bit_data, True)
    self.commands['lnote'] = Command("加载元数据", 1, "<文件名>", self.do_load_meta, True)
    self.commands['snote'] = Command("保存元数据", 1, "<文件名>", self.do_save_meta, True)
    self.commands['load'] = Command("从文件加载回访数据到缓冲区", 1, "<文件名1> [,文件名2,...] ", self.load_rep, True)
    self.commands['save'] = Command("保存缓冲区数据 (如果索引为空则保存所有)", 1, " <文件名>, [缓冲区索引]", self.do_dump_replay, True)
    self.commands['save2'] = Command("保存缓冲区基本内容到CSV文件 (如果索引为空则保存所有)", 1, " <文件名>, [缓冲区索引]", self.do_dump_csv, True)
    self.commands['save3'] = Command("保存缓冲区全部内容到CSV文件 (如果索引为空则保存所有)", 1, " <文件名>, [缓冲区索引]", self.do_dump_csv2, True)
    self.commands['delay'] = Command("获取'ping/fuzz'的延迟值", 1, "<总线速率(KB/s)>", self.get_delay, True)

  def do_activate(self, mode=-1):
    """
    实现激活或者反激活模块。
    """
    if mode == -1:
      self._active = not self._active
    elif mode == 0:
      self._active = False
    else:
      self._active = True
    self.all_frames[-1]['buf'].add_timestamp()
    result_str = '激活'
    if not self._active:
      result_str = '未激活'
    return CmdResult(cmdline='switch ' + str(mode), describe="激活状态", result_type=CMDRES_STR, result=result_str)

  def get_status(self):
    """
    获取分析模块的状态。
    """
    status = "当前状态: " + "\n统计自动分析运行状态:" + str(self._active_check) + "\n缓存的所有CAN数据帧: " + str(self.get_num(-1)) + "\n当前缓存: 索引 - " + str(self._index) + " 名称 - " + self.all_frames[self._index]['name'] + \
            "\n所有的缓冲区: \n\t" + \
            '\n\t'.join([buf['name'] + "\n\t\t索引: " + str(cnt) + ' 当前缓存计数: ' + str(len(buf['buf'])) for buf, cnt in zip(self.all_frames, range(0, len(self.all_frames)))])
    return CmdResult(cmdline='status', describe="当前状态", result_type=CMDRES_STR, result=status)

  def change_shift(self, val):
      """
      设置UDS偏移值
      u [偏移值]

      val: 偏移值，通常为8
      """
      value = int(val.strip(), 0)
      self.shift = value
      return CmdResult(cmdline='uds ' + val, describe="UDS偏移", result_type=CMDRES_STR, result=str(hex(self.shift)))




  def get_meta_descr(self, fid, msg):
      """
      通过(fid, msg)来获取在元数据保存的描述数据。
      """
      descrs = self.meta_data.get('description', {})
      #
      # 遍历元数据描述区域
      # 如果fid匹配，则在数据中寻找与参数指定内容匹配的包
      #
      for (key, body) in list(descrs.keys()):
          if fid == key:
              if re.match(body, self.get_hex(msg), re.IGNORECASE):
                  return str(descrs[(key, body)])
      return "  "

  def get_meta_bits(self, fid, length):
      """
      获取元数据中的'bits'字段
      元数据中的'bits'字段保存了以(fid, length)为KEY的位长度数据。
      """
      return self.meta_data.get('bits', {}).get((fid, length), None)

  def get_meta_all_bits(self):
      return self.meta_data.get('bits', {})

  @staticmethod
  def ret_ascii(text_array):
      """
      将参数队列数据转换成字符串。
      """
      return_str = ""
      for byte in text_array:
          if 31 < byte < 127:
              return_str += chr(byte)
          else:
              return_str += '.'
      return return_str

  @staticmethod
  def is_ascii(text_array):
      """
      判断当前的数据是否是一个标准ascii数据。
      是则返回True,反之False。
      """
      bool_ascii = False
      ascii_cnt = 0
      pre_byte = False

      for byte in text_array:
          if 31 < byte < 127:
              if pre_byte:
                  ascii_cnt += 1
                  if ascii_cnt > 1:
                      bool_ascii = True
                      break
              else:
                  pre_byte = True
          else:
              pre_byte = False
              ascii_cnt = 0

      if ascii_cnt > 5:
          bool_ascii = True

      return bool_ascii

  def get_num(self, _index=-1):
      count = 0
      if _index == -1:
          for buf in self.all_frames:
              count += len(buf['buf'])
      else:
          count = len(self.all_frames[_index]['buf'])

      return count

  @staticmethod
  def create_short_table(input_frames):
      """
      将缓冲区形成一个字典表，便于之后的分析。
      """
      _bodyList = collections.OrderedDict()
      # 遍历所有的输入帧
      for timestmp, can_msg in input_frames:

          # 如果是CAN数据
          if can_msg.CANData:
              # 如果是新的CANID则创建一个新的有序字典结构
              if can_msg.CANFrame.frame_id not in _bodyList:
                  _bodyList[can_msg.CANFrame.frame_id] = collections.OrderedDict()
                  _bodyList[can_msg.CANFrame.frame_id][(
                      can_msg.CANFrame.frame_length,
                      can_msg.CANFrame.frame_raw_data,
                      can_msg.bus,
                      can_msg.CANFrame.frame_ext)] = 1
              else:
                  #
                  # 如果是已经保存过的CANID则分两种情况
                  # 1. 数据是新的数据则保存新数据
                  # 2. 数据是曾经见过的数据则增加引用次数
                  #
                  if (can_msg.CANFrame.frame_length,
                          can_msg.CANFrame.frame_raw_data,
                          can_msg.bus,
                          can_msg.CANFrame.frame_ext) not in _bodyList[can_msg.CANFrame.frame_id]:
                      _bodyList[can_msg.CANFrame.frame_id][(
                          can_msg.CANFrame.frame_length,
                          can_msg.CANFrame.frame_raw_data,
                          can_msg.bus,
                          can_msg.CANFrame.frame_ext)] = 1
                  else:
                      _bodyList[can_msg.CANFrame.frame_id][(
                          can_msg.CANFrame.frame_length,
                          can_msg.CANFrame.frame_raw_data,
                          can_msg.bus,
                          can_msg.CANFrame.frame_ext)] += 1
      return _bodyList

  @staticmethod
  def find_iso_tp(in_list):
      """
      在缓冲区中找寻isotp协议包
      """
      message_iso = {}
      iso_list = []
      # 遍历缓冲区
      for _, can_msg in in_list:
          # 如果是CAN数据
          if can_msg.CANData:
              # 如果发现CANID不在ISO消息列表中则将当前的CAN数据转换成ISO数据包
              if can_msg.CANFrame.frame_id not in message_iso:
                  message_iso[can_msg.CANFrame.frame_id] = ISOTPMessage(can_msg.CANFrame.frame_id)

              # 如果当前的CAN数据大于1
              if 1 < can_msg.CANFrame.frame_length:
                  # 通过add_can来判断当前CAN数据是否是一个ISOTP协议
                  ret = message_iso[can_msg.CANFrame.frame_id].add_can(can_msg.CANFrame)
                  if ret < 0:
                      del message_iso[can_msg.CANFrame.frame_id]
                  elif ret == 1:
                      iso_list.append(message_iso[can_msg.CANFrame.frame_id])
                      del message_iso[can_msg.CANFrame.frame_id]
              else:
                  # 小于1则忽略当前的CAN数据，因为ISO数据长度必然大于1
                  del message_iso[can_msg.CANFrame.frame_id]
      return iso_list

  def find_uds(self, iso_list):
      """
      将ISOTP包中的UDS包转换成UDS包
      非UDS包则在对应队列索引处标记为False。
      """
      uds_list = UDSMessage(self.shift)
      for message_iso in iso_list:
          uds_list.handle_message(message_iso)
      return uds_list

  def find_loops(self):
      """
      遍历当前构建的_bodyList(分析表)
      将表中的CAN数据全部提取出来并存入一个FragmentedCAN类队列中。
      """
      frg_list = collections.OrderedDict()
      for fid, lst in self._bodyList.items():
          frg_list[fid] = FragmentedCAN()
          for (lenX, msg, bus, mod), cnt in lst.items():
              frg_list[fid].add_can_loop(CANMessage.init_data(fid, lenX, msg))

      return frg_list

  def _anal_uds(self, uds):
      """对CAN消息执行UDS分析

      :param dict uds: UDS消息的字典结构

      :return: CAN消息的分析结果
      :rtype: str
      """
      result = 'UDS Detected:\n\n'
      # 遍历UDS列表
      for fid, services in uds.sessions.items():
          for service, sub in services.items():
              for sub_id, body in sub.items():
                  text = '(未知)'
                  # Well-known and defined UDS service (e.g. Diagnostic Session Control)
                  # 在已知的服务表中
                  if service in UDSMessage.services_base:
                      # 取出服务名称
                      subservice_name = UDSMessage.services_base[service].get(None, '未知') 
                      service_name = UDSMessage.services_base[service].get(sub_id, subservice_name)
                      text = '({})'.format(service_name)

                  #
                  # 通过'status'字段，判别不同的状态来填写分析结果
                  #
                  if body['status'] == 1:
                      data = body['response']['data']
                      data2 = body['data']
                      data_ascii = ''
                      data_ascii2 = ''
                      if self.is_ascii(data2):
                          data_ascii2 = '\n\t\t字符: {}\n'.format(self.ret_ascii(data2))
                      if self.is_ascii(body['response']['data']):
                          data_ascii = '\n\t\t字符: {}\n'.format(self.ret_ascii(data))
                      result += '\n\tID: {} 服务: {} 子服务: {} {}'.format(
                          hex(fid), hex(service), hex(sub_id) if sub_id < 0x100 else '无子服务', text)
                      result += '\n\t\t请求: {}'.format(self.get_hex(bytes(data2)) + data_ascii2)
                      result += '\n\t\t回应: {}\n'.format(self.get_hex(bytes(data)) + data_ascii)
                  elif body['status'] == 2:
                      data2 = body['data']
                      data_ascii2 = ''
                      if self.is_ascii(data2):
                          data_ascii2 = '\n\t\t字符: {}\n'.format(self.ret_ascii(data2))
                      result += '\n\tID: {} 服务: {} 子服务: {} {}'.format(
                          hex(fid), hex(service), hex(sub_id) if sub_id < 0x100 else '(当无子服务时的另外一种解释)', text)
                      result += '\n\t\t请求: {}'.format(self.get_hex(bytes(data2)) + data_ascii2)
                      result += '\n\t\t错误: {}\n'.format(body['response']['error'])
      return result

  def _anal_frag(self, loops):
      """对CAN消息执行分析

      :param dict loops: CAN消息字典

      :return: 分析结果字符串
      :rtype: str
      """
      result = "\n\n解析CAN数据帧 (使用循环检测):\n"
      local_temp = {}
      for fid, data in loops.items():
          data.clean_build_loop()
          for message in data.messages:
              if (fid, bytes(message['message_data'])) not in local_temp:
                  result += '\n\tID {} 与 长度 {}\n'.format(hex(fid), message['message_length'])
                  result += '\t\t数据: {}'.format(self.get_hex(bytes(message['message_data'])))
                  if self.is_ascii(message['message_data']):
                      result += '\n\t\t字符: {}\n\n'.format(self.ret_ascii(bytes(message['message_data'])))
                  local_temp[(fid, bytes(message['message_data']))] = None
      return result

  def _anal_iso(self, iso):
      """对CAN消息执行ISOTP分析

      :param dict iso: 消息字典

      :return: 分析结果字符串
      :rtype: str
      """
      result = '\nISO TP 消息:\n\n'
      for fid, lst in iso.items():
          result += '\tID: {}\n'.format(hex(fid))
          for (_, msg), _ in lst.items():
              result += '\t\t数据: ' + self.get_hex(msg)
              if self.is_ascii(msg):
                  result += '\n\t\t字符: {}'.format(self.ret_ascii(msg))
              result += '\n'
      return result

  def do_anal(self, pformat='ALL'):
      """对捕获的格式进行分析，以检测UDS、ISOTP和片段化的CAN帧。

      :param pformat: 检测格式 ('ALL', 'UDS', 'ISO', 'FRAG')

      :return: 当前分析的信息
      :rtype: str
      """
      params = pformat.upper().split(',')
      # 通过参数提取出格式参数格式为 "格式 缓冲区索引"
      _format = params[0].strip()         # 取出格式
      _index = -1
      if len(params) > 1:
          _index = int(params[1])         # 取出缓冲区索引

      temp_buf = Replay()

      # 如果索引为-1则收集所有缓冲区
      if _index == -1:
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          temp_buf = self.all_frames[_index]['buf']

      # 创建分析表
      self._bodyList = self.create_short_table(temp_buf)

      #
      # 将缓冲区中的ISOTP协议包与UDS协议包提取出来
      # 并将所有CAN数据提取到数据帧结构队列loops_list
      #
      iso_tp_list = self.find_iso_tp(temp_buf)
      uds_list = self.find_uds(iso_tp_list)
      loops_list = self.find_loops()
      ret_str = ""

      #
      # 建立一个当前要分析缓冲区的ISOTP索引表
      # {
      #   message_id : 
      #   {
      #       (message_length, message_data) : 引用次数        
      #   }
      # }
      #
      _iso_tbl = collections.OrderedDict()
      for msg in iso_tp_list:
          if msg.message_id not in _iso_tbl:
              _iso_tbl[msg.message_id] = collections.OrderedDict()
              _iso_tbl[msg.message_id][(msg.message_length, bytes(msg.message_data))] = 1
          else:
              if (msg.message_length, bytes(msg.message_data)) in _iso_tbl[msg.message_id]:
                  _iso_tbl[msg.message_id][(msg.message_length, bytes(msg.message_data))] += 1
              else:
                  _iso_tbl[msg.message_id][(msg.message_length, bytes(msg.message_data))] = 1

      #
      # 按照指定的格式，进行分析并将结构保存到字符串中
      #
      if _format in ['UDS', 'ALL']:
          ret_str += self._anal_uds(uds_list)
      if _format in ['FRAG', 'ALL']:
          ret_str += self._anal_frag(loops_list)
      if _format in ['ISO', 'ALL']:
          ret_str += self._anal_iso(_iso_tbl)
      return CmdResult(cmdline='protocol ' + pformat, describe="协议分析结果", result_type=CMDRES_STR, result=ret_str)

  def search_id(self, idf):
      """
      在所有缓冲区中搜索索引

      search <索引>
      """
      idf = int(idf.strip(), 0)       # 自动解释基
      table = "搜索'CANID': " + hex(idf) + "\n"
      rows = []
      # 在所有的缓冲区中找寻指定CANID的数据包
      for buf in self.all_frames:
          rows.append(['Dump:', buf['name'], ' ', ' ', ' ', ' ', ' '])
          rows.append(['BUS', 'ID', 'LENGTH', 'MESSAGE', 'ASCII', 'DESCR', 'COUNT'])
          #rows.append(['BUS', 'ID', '长度', '数据', '字符', '描述', '计数'])
          short = self.create_short_table(buf['buf'])
          if idf in short:
              for (lenX, msg, bus, mod), cnt in short[idf].items():
                  if self.is_ascii(msg):
                      data_ascii = self.ret_ascii(msg)
                  else:
                      data_ascii = "  "
                  rows.append([str(bus), hex(idf), str(lenX), self.get_hex(msg), data_ascii, self.get_meta_descr(idf, msg), str(cnt)])
      cols = list(zip(*rows))
      col_widths = [max(len(value) for value in col) for col in cols]
      format_table = '    '.join(['%%-%ds' % width for width in col_widths])
      for row in rows:
          table += format_table % tuple(row) + "\n"
      table += "\n"
      return CmdResult(cmdline='search ' + str(idf), describe="搜索结果", result_type=CMDRES_STR, result=table)

  def print_dump_diff(self, name):
      """
      在回放模式中对比不同，如果不指定表1,会将默认使用表2 - 1作为索引作为表1的索引。
      并将不同保存到回访文件中。

      rdiff <文件名> [缓冲区1的索引], [缓冲区2的索引], [对比数据的最大范围(字节)]
      """
      ret = self.print_dump_diff_(name, 0)
      return CmdResult(cmdline='rdiff ' + name, describe="缓存对比结果", result_type=CMDRES_STR, result=ret)

  def print_dump_diff_id(self, name):
      """
      在回放模式中对比不同，如果不指定表1,会将默认使用表2 - 1作为索引作为表1的索引。
      并将不同保存到回访文件中。此功能不检索内容，仅仅使用ID进行匹配。

      rdiff2 <文件名> [缓冲区1的索引], [缓冲区2的索引]
      """
      ret = self.print_dump_diff_(name, 1)
      return CmdResult(cmdline='rdiff2 ' + name, describe="缓存对比结果", result_type=CMDRES_STR, result=ret)

  def print_dump_diff_(self, name, mode=0):
      """
      在回放模式中对比不同，如果不指定表1,会将默认使用表2 - 1作为索引作为表1的索引。
      并将不同保存到回访文件中。

      diff/rdiff <文件名> [缓冲区1的索引], [缓冲区2的索引], [对比数据的最大范围(字节)]
      """
      inp = name.split(",")
      if len(inp) == 4:
          name = inp[0].strip()
          idx1 = int(inp[1])
          idx2 = int(inp[2])
          rang = int(inp[3])
      elif len(inp) == 3:
          name = inp[0].strip()
          idx1 = int(inp[1])
          idx2 = int(inp[2])
          rang = 8 * 256
      else:
          name = inp[0].strip()
          idx2 = self._index
          idx1 = self._index - 1 if self._index - 1 >= 0 else 0
          rang = 8 * 256

      table1 = self.create_short_table(self.all_frames[idx1]['buf'])          # 表1
      tblDif = self.all_frames[idx2]['buf'] + self.all_frames[idx1]['buf']    # 表1 + 表2
      table2 = self.create_short_table(tblDif)
      try:
          dump = Replay()
          dump.add_timestamp()
          tms = 0.0
          # 以表2为基础遍历与表1做对比
          for timestmp, can_msg in self.all_frames[idx2]['buf']:
              if can_msg.CANData:
                  if tms == 0.0:
                      tms = timestmp
                  if can_msg.CANFrame.frame_id not in list(table1.keys()):
                      dump.append_time(timestmp - tms, can_msg)
                  elif mode == 0 and len(table2[can_msg.CANFrame.frame_id]) <= rang:
                      # 对比内容
                      neq = True
                      for (len2, msg, bus, mod), cnt in table1[can_msg.CANFrame.frame_id].items():
                          # 如果数据相同则跳过
                          if msg == can_msg.CANFrame.frame_raw_data:
                              neq = False
                      # 仅在数据不同时添加
                      if neq:
                          dump.append_time(timestmp - tms, can_msg)
              elif can_msg.debugData:
                  dump.add_timestamp()
                  tms = 0.0
          dump.save_dump(name)
      except Exception as e:
          return str(e)
      return "保存到文件 " + name

  def do_dump_replay(self, name):
      inp = name.split(",")
      if len(inp) == 2:
          name = inp[0].strip()
          idx1 = int(inp[1])
      else:
          name = inp[0].strip()
          idx1 = -1

      temp_buf = Replay()
      if idx1 == -1:
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          temp_buf = self.all_frames[idx1]['buf']

      try:
          ret = temp_buf.save_dump(name)
      except Exception as e:
          return CmdResult(cmdline='save ' + name, describe="不能打开保存文件", last_error=-2, e=e)
      return CmdResult(cmdline='save ' + name, describe="保存到文件", result_type=CMDRES_STR, result=name)

  @staticmethod
  def escape_csv(_string):
      return '"' + _string.replace('"', '""') + '"'

  def do_dump_csv2(self, name):
      inp = name.split(",")
      if len(inp) == 2:
          name = inp[0].strip()
          idx1 = int(inp[1])
      else:
          name = inp[0].strip()
          idx1 = -1

      temp_buf = Replay()
      if idx1 == -1:
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          temp_buf = self.all_frames[idx1]['buf']

      self._bodyList = self.create_short_table(temp_buf)
      try:
          descr = ""
          bitzx = self.get_meta_all_bits()
          for (fid, flen), body in bitzx.items():
              for bt in body:
                  descr += "," + str(fid) + "_" + list(list(bt.values())[0].values())[0]

          _name = open(name.strip(), 'w')
          _name.write("TIME,BUS,ID,LENGTH,DATA_BYTE1,DATA_BYTE2,DATA_BYTE3,DATA_BYTE4,DATA_BYTE5,DATA_BYTE6,DATA_BYTE7,DATA_BYTE8,ASCII,COMMENT" + descr + "\n")

          for times, msg in temp_buf._stream:
              if not msg.debugData and msg.CANData:
                  data = msg.CANFrame.frame_data[:msg.CANFrame.frame_length] + ([0] * (8 - msg.CANFrame.frame_length))

                  data_ascii = self.escape_csv(self.ret_ascii(msg.CANFrame.frame_raw_data)) if self.is_ascii(msg.CANFrame.frame_raw_data) else "  "

                  format_ = self.get_meta_bits(msg.CANFrame.frame_id, msg.CANFrame.frame_length)

                  filds = ""
                  if format_:
                      idx_0 = 0
                      for bitz in format_:
                          fmt = list(bitz.keys())[0]
                          idx = list(list(bitz.values())[0].keys())[0]
                          filds += "," + self.get_data_in_format(msg.CANFrame.frame_raw_data, idx_0, idx, fmt)
                          idx_0 = idx

                  _name.write(
                      str(round(times, 4)) + ',' +
                      str(msg.bus) + ',' +
                      str(msg.CANFrame.frame_id) + ',' +
                      str(msg.CANFrame.frame_length) + ',' +
                      str(data[0]) + ',' +
                      str(data[1]) + ',' +
                      str(data[2]) + ',' +
                      str(data[3]) + ',' +
                      str(data[4]) + ',' +
                      str(data[5]) + ',' +
                      str(data[6]) + ',' +
                      str(data[7]) + ',' +
                      data_ascii + ',' +
                      self.get_meta_descr(msg.CANFrame.frame_id, msg.CANFrame.frame_raw_data) + filds + "\n"
                  )
          _name.close()
      except Exception as e:
          return CmdResult(cmdline='save3 ' + name, describe="不能打开保存文件", last_error=-2, e=e)
      return CmdResult(cmdline='save3 ' + name, describe="保存到文件", result_type=CMDRES_STR, result=name.strip())

  def do_dump_csv(self, name):
      inp = name.split(",")
      if len(inp) == 2:
          name = inp[0].strip()
          idx1 = int(inp[1])
      else:
          name = inp[0].strip()
          idx1 = -1

      temp_buf = Replay()
      if idx1 == -1:
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          temp_buf = self.all_frames[idx1]['buf']

      self._bodyList = self.create_short_table(temp_buf)
      try:
          _name = open(name.strip(), 'w')
          _name.write("BUS,ID,LENGTH,MESSAGE,ASCII,COMMENT,COUNT\n")
          for fid, lst in self._bodyList.items():
              for (lenX, msg, bus, mod), cnt in lst.items():

                  format_ = self.get_meta_bits(fid, lenX)
                  if not format_:
                      if self.is_ascii(msg):
                          data_ascii = self.escape_csv(self.ret_ascii(msg))
                      else:
                          data_ascii = "  "
                      _name.write(
                          str(bus) + "," + hex(fid) + "," + str(lenX) + "," + self.get_hex(msg) + ',' + data_ascii + ',' +
                          "\"" + self.escape_csv(self.get_meta_descr(fid, msg)) + "\"" + ',' + str(cnt) + "\n")
                  else:
                      idx_0 = 0
                      msg_s = ""
                      for bitz in format_:
                          fmt = list(bitz.keys())[0]
                          idx = list(list(bitz.values())[0].keys())[0]
                          descr = list(list(bitz.values())[0].values())[0]
                          msg_s += descr + ": " + self.get_data_in_format(msg, idx_0, idx, fmt) + " "
                          idx_0 = idx
                      _name.write(
                          str(bus) + "," + hex(fid) + "," + str(lenX) + "," + msg_s + ',' + " " + ',' +
                          "\"" + self.escape_csv(self.get_meta_descr(fid, msg)) + "\"" + ',' + str(cnt) + "\n")
          _name.close()
      except Exception as e:
          return CmdResult(cmdline='save2 ' + name, describe="不能打开保存文件", last_error=-2, e=e)
      return CmdResult(cmdline='save2 ' + name, describe="保存到文件", result_type=CMDRES_STR, result=name.strip())

  def print_diff(self, inp=""):
      """
      打印缓冲区的不同

      I 缓冲区1索引, 缓冲区2索引, 范围
      如果不指定缓冲区2的索引则使用当前最后一个缓冲区
      如果不指定范围则使用8*256
      """
      _inp = inp.split(",")
      if len(_inp) == 3:
          idx1 = int(_inp[0])
          idx2 = int(_inp[1])
          rang = int(_inp[2])
      elif len(_inp) == 2:
          idx1 = int(_inp[0])
          idx2 = int(_inp[1])
          rang = 8 * 256
      else:
          idx2 = self._index
          idx1 = self._index - 1 if self._index - 1 >= 0 else 0
          rang = 8 * 256
      
      ret = self.print_diff_orig(0, idx1, idx2, rang)
      return CmdResult(cmdline='diff ' + inp, describe="缓存对比结果", result_type=CMDRES_STR, result=ret)

  def print_diff_id(self, inp=""):
      """
      与print_diff 一样, 但是仅对比缓冲区1中与缓冲区2中的ID是否相同，不匹配内容

      N 缓冲区1索引, 缓冲区2索引
      """
      _inp = inp.split(",")
      if len(_inp) != 2:
          idx2 = self._index
          idx1 = self._index - 1 if self._index - 1 >= 0 else 0
      else:
          idx2 = int(_inp[1])
          idx1 = int(_inp[0])
      ret = self.print_diff_orig(1, idx1, idx2, 8 * 256)
      return CmdResult(cmdline='diff2 ' + inp, describe="缓存对比结果", result_type=CMDRES_STR, result=ret)

  def print_diff_orig(self, mode, idx1, idx2, rang):
      """
      打印对比两个缓冲区的不同

      mode: 模式:如果为0则表示如果id相同则匹配内容，如果非0则只匹配ID
      idx1: 缓冲区1索引
      idx2: 缓冲区2索引
      rang: 范围
      """
      # 按照缓冲区建立分析表
      table1 = self.create_short_table(self.all_frames[idx1]['buf'])      # 表1
      table2 = self.create_short_table(self.all_frames[idx2]['buf'])      # 表2
      table3 = self.create_short_table(self.all_frames[idx1]['buf'] + self.all_frames[idx2]['buf'])   # 表1 + 表2
      #table = " DIFF sets between " + self.all_frames[idx1]['name'] + " and " + self.all_frames[idx2]['name'] + "\n"
      rows = [['BUS', 'ID', 'LENGTH', 'MESSAGE', 'ASCII', 'DESCR', 'COUNT']]
      table = " 对比不同在 " + self.all_frames[idx1]['name'] + " 与 " + self.all_frames[idx2]['name'] + "\n"
      #rows = [['BUS', 'ID', '长度', '数据', '字符', '描述', '计数']]

      #
      # 以表2为基础进行匹配
      #
      for fid2, lst2 in table2.items():
          # 如果表2的id不在表1中
          if fid2 not in list(table1.keys()):
              # 打印结果
              for (lenX, msg, bus, mod), cnt in lst2.items():
                  if self.is_ascii(msg):
                      data_ascii = self.ret_ascii(msg)
                  else:
                      data_ascii = "  "
                  rows.append([str(bus), hex(fid2), str(lenX), self.get_hex(msg), data_ascii, self.get_meta_descr(fid2, msg), str(cnt)])
          # 如果表2的id在表1中则匹配范围内
          elif mode == 0 and len(table3[fid2]) <= rang:
              for (lenX, msg, bus, mod), cnt in lst2.items():
                  # 在许可范围内，内容与表1中的内容不一样
                  if (lenX, msg, bus, mod) not in table1[fid2]:
                      if self.is_ascii(msg):
                          data_ascii = self.ret_ascii(msg)
                      else:
                          data_ascii = "  "
                      rows.append([str(bus), hex(fid2), str(lenX), self.get_hex(msg), data_ascii, self.get_meta_descr(fid2, msg), str(cnt)])

      cols = list(zip(*rows))
      col_widths = [max(len(value) for value in col) for col in cols]
      format_table = '    '.join(['%%-%ds' % width for width in col_widths])
      for row in rows:
          table += format_table % tuple(row) + "\n"
      table += "\n"
      return table

  def new_diff(self, name=""):
      # 新建一个缓冲区
      _name = name.strip()
      _name = _name if _name != "" else "buffer_" + str(len(self.all_frames))
      self._index += 1
      self.all_frames.append({'name': _name, 'buf': Replay()})
      self.all_frames[-1]['buf'].add_timestamp()
      result_str = "当前缓冲区索引 : " + str(self._index)
      return CmdResult(cmdline='newbuf ' + name, describe="新的缓存", result_type=CMDRES_STR, result=result_str)

  def do_print(self, index="-1"):
      _index = int(index)
      temp_buf = Replay()
      # 如果参数为-1则打印所有缓冲区
      if _index == -1:
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          # 获取指定的缓冲区
          temp_buf = self.all_frames[_index]['buf']

      # 创建分析表
      self._bodyList = self.create_short_table(temp_buf)

      #
      # 将分析表转换成字符串形式
      #
      table = "\n"
      rows = [['BUS', 'ID', 'LENGTH', 'MESSAGE', 'ASCII', 'DESCR', 'COUNT']]
      #rows = [['BUS', 'ID', '长度', '数据', '字符', '描述', '计数']]
      # http://stackoverflow.com/questions/3685195/line-up-columns-of-numbers-print-output-in-table-format
      for fid, lst in self._bodyList.items():
          for (lenX, msg, bus, mod), cnt in lst.items():
              # 按照当前的(fid, lenX)找寻对应的位长度
              format_ = self.get_meta_bits(fid, lenX)

              # 如果没有找到
              if not format_:
                  if self.is_ascii(msg):
                      # 转换成字符串
                      data_ascii = self.ret_ascii(msg)
                  else:
                      data_ascii = "  "
                  rows.append([str(bus), hex(fid), str(lenX), self.get_hex(msg), data_ascii, self.get_meta_descr(fid, msg), str(cnt)])
              else:
                  #
                  # 这里按照格式取出描述以及数据内容
                  #
                  idx_0 = 0
                  msg_s = ""
                  for bitz in format_:
                      fmt = list(bitz.keys())[0]
                      idx = list(list(bitz.values())[0].keys())[0]
                      descr = list(list(bitz.values())[0].values())[0]
                      msg_s += descr + ": " + self.get_data_in_format(msg, idx_0, idx, fmt) + " "
                      idx_0 = idx
                  rows.append([str(bus), hex(fid), str(lenX), msg_s, " ", self.get_meta_descr(fid, msg), str(cnt)])

      # 这里是制表操作
      cols = list(zip(*rows))
      col_widths = [max(len(value) for value in col) for col in cols]
      format_table = '    '.join(['%%-%ds' % width for width in col_widths])
      for row in rows:
          table += format_table % tuple(row) + "\n"
      table += ""
      return CmdResult(cmdline='print ' + index, describe="缓冲区表", result_type=CMDRES_STR, result=table)

  def do_effect(self, can_msg, args):
      if self._need_status and not self._action.is_set():
          self._action.set()
          self._status = self._last / (self._full / 100.0)
          self._action.clear()

      # 这里判断当前数据为CAN或者是调试数据，并且没有不读标记添加添加包
      if (can_msg.CANData or can_msg.debugData) and args.get('action', 'read') == 'read':
          self.all_frames[self._index]['buf'].append(can_msg)

      # 如果非分析引擎关注数据直接写入CAN数据并向下传递
      elif not can_msg.CANData and not can_msg.debugData and args.get('action', 'read') == 'write' and not self._action.is_set():
          self._action.set()
          if self._stat_resend:
              can_msg.CANData = True
              can_msg.CANFrame = copy.deepcopy(self._stat_resend)
              can_msg.bus = self._bus
              self._stat_resend = None
          self._action.clear()

      return can_msg

  def get_data_in_format(self, data, idx_1, idx_2, format):
      selected_value_hex = bitstring.BitArray('0b' + ('0' * ((4 - ((idx_2 - idx_1) % 4)) % 4)) + bitstring.BitArray(data)[idx_1:idx_2].bin)
      selected_value_bin = bitstring.BitArray('0b' + bitstring.BitArray(data)[idx_1:idx_2].bin)
      if format.strip() in ["bin", "b", "binary"]:
          return selected_value_bin.bin
      elif format.strip() in ["hex", "h"]:
          return selected_value_hex.hex
      elif format.strip() in ["int", "i"]:
          return str(selected_value_hex.int)
      elif format.strip() in ["ascii", "a"]:
          return self.ret_ascii(selected_value_bin.bytes)
      else:
          return selected_value_hex.hex

  def show_fields_ecu(self, ecu_id):
      """
      显示某个ECU的数据字段, ecu_id : ECUID,<bin|hex|int|ascii>,缓冲区索引
      """
      _index = -1
      fformat = "bin"
      if len(ecu_id.strip().split(",")) == 2:
          fformat = str(ecu_id.strip().split(",")[1].strip())
      elif len(ecu_id.strip().split(",")) == 3:
          _index = int(ecu_id.strip().split(",")[2])          # 缓冲区索引
          fformat = ecu_id.strip().split(",")[1].strip()      # 显示格式

      ecu_id = ecu_id.strip().split(",")[0]                   # ECU ID
      ecu_id = int(ecu_id, 0)

      #table = "Data by fields in ECU: " + hex(ecu_id) + "\n\n"
      table = "ECU的数据字段: " + hex(ecu_id) + "\n\n"
      temp_buf = Replay()

      #
      # 统计数据区域
      #
      self.show_fields(str(_index))

      #
      # 组合缓冲区
      #
      if _index == -1:
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          temp_buf = self.all_frames[_index]['buf']

      #
      # 建立缓冲表
      #
      _bodyList = self.create_short_table(temp_buf)
      list_idx = {}

      #
      # 遍历所有项
      #
      for key, value in self.subnet._devices.items():
          _ecu_id = int(str(key).split(':')[0], 0)
          # 匹配到指定的 ecu_id
          if _ecu_id == ecu_id:
              list_idx[int(str(key).split(":")[1])] = [value._indexes()]

      if ecu_id in _bodyList:
          #
          # 遍历当前CANID的所有内容
          #
          for (lenX, msg, bus, mod), cnt in _bodyList[ecu_id].items():
              tmp_f = []
              idx_0 = 0
              for idx in list_idx[lenX][0]:
                  tmp_f.append(self.get_data_in_format(msg, idx_0, idx, fformat))
                  idx_0 = idx
              list_idx[lenX].append(tmp_f)

      for lenY, msg in list_idx.items():
          #table += "\nby length: " + str(lenY) + "\n\n"
          table += "\n根据数据长度: " + str(lenY) + "\n\n"
          cols = list(zip(*msg[1:]))
          col_widths = [max(len(value) for value in col) for col in cols]
          format_table = '    '.join(['%%-%ds' % width for width in col_widths])
          for ms in msg[1:]:
              table += format_table % tuple(ms) + "\n"
          table += ""
      return CmdResult(cmdline='fields ' + str(ecu_id), describe="数据字段, ECU : " + str(ecu_id), result_type=CMDRES_STR, result=table)

  def show_fields(self, _index="-1"):
      """
      显示所有已经检测ECU的变量
      """
      table = ""

      _index = int(_index)
      temp_buf = Replay()
      if _index == -1:
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          temp_buf = self.all_frames[_index]['buf']

      for timestmp, can_msg in temp_buf:
          if can_msg.CANData:
              for _ in self.subnet.process(can_msg.CANFrame):
                  pass
      rows = []
      for key, value in self.subnet._devices.items():
          self.info(value)
          rows.append(["ECU: " + str(key).split(":")[0], " 长度: " + str(key).split(":")[1], " 字段检测: " + str(len(value._indexes()))])
          #for i in value._indexes():
          #    print("key = {}, i = {}".format(str(key), i))

      cols = list(zip(*rows))
      col_widths = [max(len(value) for value in col) for col in cols]
      format_table = '    '.join(['%%-%ds' % width for width in col_widths])
      for row in rows:
          table += format_table % tuple(row) + "\n"
      table += ""
      table = "检测到的ECU变量\n\n" + table
      return CmdResult(cmdline='fields ' + str(_index), describe="数据字段", result_type=CMDRES_STR, result=table)

  def show_change(self, _index="-1"):
      """
      探测ECU的改变,这里以message:length 作为健, 数据作为值来进行索引。

      change 缓冲区索引,最大发生改变的次数
      """
      table = ""
      pars = _index.split(",")
      depth = 31337

      if len(pars) == 2:
          depth = int(pars[1])
          _index = pars[0].strip()

      _index = int(_index)
      temp_buf = Replay()
      if _index == -1:
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          temp_buf = self.all_frames[_index]['buf']

      messages = collections.OrderedDict()

      # 遍历缓冲区
      for timestmp, can_msg in temp_buf:
          if can_msg.CANData:
              #
              # CANID没有遇到过则建立(id, lenght) : message 这样的索引
              # 这条if是创建新的字典项目
              #
              if (can_msg.CANFrame.frame_id, can_msg.CANFrame.frame_length) not in messages:
                  messages[(can_msg.CANFrame.frame_id, can_msg.CANFrame.frame_length)] = [[can_msg.CANFrame.frame_raw_data], 0, 1]
              else:
                  #
                  # 如果CANID之前遇到过，则追加在此CANID,length为键的数据
                  #
                  messages[(can_msg.CANFrame.frame_id, can_msg.CANFrame.frame_length)][0].append(can_msg.CANFrame.frame_raw_data)
                  #
                  # 这里对比当前新添加的与上一个包是否相同，如果不相同则增加改变次数
                  #
                  if messages[(can_msg.CANFrame.frame_id, can_msg.CANFrame.frame_length)][0][-1] != messages[(can_msg.CANFrame.frame_id, can_msg.CANFrame.frame_length)][0][-2]:
                      messages[(can_msg.CANFrame.frame_id, can_msg.CANFrame.frame_length)][1] += 1
                  #
                  # 这里对比当前新添加的包在之前所有包中都没出现则唯一包计数添加1
                  #
                  if messages[(can_msg.CANFrame.frame_id, can_msg.CANFrame.frame_length)][0][-1] not in messages[(can_msg.CANFrame.frame_id, can_msg.CANFrame.frame_length)][0][:-1]:
                      messages[(can_msg.CANFrame.frame_id, can_msg.CANFrame.frame_length)][2] += 1

      #table += "Detected changes (two values):\n\n"
      table += "检查改变 (双值):\n\n"
      for (fid, flen), data in messages.items():
          msgs = len(data[0])     # 数据
          chgs = data[1]          # 发生改变的次数
          uniq = data[2]          # 有多少个没有发生改变的包(唯一的包)
          if uniq > 1 and msgs > 3 and uniq <= depth:
              #table += "\t " + hex(fid) + " count of uniq. values: " + str(uniq) + " values/uniq.: " + str(round(float(msgs / uniq), 2)) + " changes/uniq.: " + (str(round(float(chgs / uniq), 2))) + "\n"
              table += "\t " + hex(fid) + " 唯一数据包个数: " + str(uniq) + " 总数据个数: " + str(msgs) + " 改变的次数: " + str(chgs) + "\n"
      return CmdResult(cmdline='change ' + str(_index), describe="数据改变", result_type=CMDRES_STR, result=table)

  def show_detect(self, args='-1'):
      """在指定的缓冲区中找寻指定的CANID与CAN数据并以此包作为分界线
      对比了前后CANID的数据的差异。

      :param str args: <CANID:HEX_DATA>, [缓冲区ID]

      :return: 输出结果
      :rtype: str
      """
      table = ''
      parts = args.split(',')
      if len(parts) == 2:
          ecu_data, index = map(str.strip, parts)
          index = int(index)
      else:
          ecu_data = parts[0].strip()
          index = -1

      # 从参数中分离CANID与数据
      fid, body = map(str.strip, ecu_data.split(':'))
      fid = int(fid, 0)
      body = bytes.fromhex(body)

      # 建立分析缓冲
      temp_buf = Replay()
      if index == -1:
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          temp_buf = self.all_frames[index]['buf']

      self.dprint(3, "index = {}, len = {}".format(index, len(temp_buf)))

      messages = collections.OrderedDict()
      status = False
      for timestmp, can_msg in temp_buf:
          # 过滤掉非CAN数据的包
          if not can_msg.CANData:
              continue

          #
          # 在当前缓冲中找到对应的包，在找到此包之前，将所有的包都放到之前的数据，
          # 匹配到此包后，将所有的包对应的放到之后的数据。
          #
          if can_msg.CANFrame.frame_id == fid and can_msg.CANFrame.frame_raw_data == body:
              status = True
              self.dprint(3, "found fid = {}".format(hex(fid)))
          else:
              # 从来没有找到过指定的数据
              if not status:
                  #
                  # CANID不在消息列表中则创建一个新的项目
                  # messages是以CANID为健，以[[之前的CAN数据], [之后的CAN数据]] 的一个字典
                  #
                  if can_msg.CANFrame.frame_id not in messages:
                      messages[can_msg.CANFrame.frame_id] = [[can_msg.CANFrame.frame_raw_data], []]
                  #
                  # CANID在消息列表但是内容不同则更新对于CANID的消息表
                  # 这里如果是内容不同，则视为一个新的内容
                  #
                  elif can_msg.CANFrame.frame_raw_data not in messages[can_msg.CANFrame.frame_id][0]:
                      messages[can_msg.CANFrame.frame_id][0].append(can_msg.CANFrame.frame_raw_data)
              else:
                  #
                  # 此包的CANID不在messages中，但是与匹配的CANID相同
                  # 保存此包到messages中，但是只是追加到 “之后的CAN数据”中
                  #
                  if can_msg.CANFrame.frame_id not in messages:
                      messages[can_msg.CANFrame.frame_id] = [[], [can_msg.CANFrame.frame_raw_data]]
                  #
                  # CANID相同,但是内容不同，追加新内容到“之后的CAN数据”中
                  #
                  elif can_msg.CANFrame.frame_raw_data not in messages[can_msg.CANFrame.frame_id][1]:
                      messages[can_msg.CANFrame.frame_id][1].append(can_msg.CANFrame.frame_raw_data)

      table += '检测到改变 (通过 ID : {} 进行分类):\n'.format(hex(fid))
      if status:
          for fid, data in messages.items():
              before, after = data[0:2]
              diff_not = False
              # 对比两个队列是否有不同
              if 0 < len(before) <= 10 and 0 < len(after) <= 10:
                  diff_not = bool([x for x in after if x not in before] != [])
              # 如果有不同则打印
              if diff_not:
                  table += '\n\t ID: {}'.format(hex(fid))
                  table += '\n\t\t 从: \n'
                  table += ''.join('\t\t{}\n'.format(self.get_hex(x)) for x in before)
                  table += '\n\t\t 改变到: \n'
                  table += ''.join('\t\t{}\n'.format(self.get_hex(x)) for x in after)
      return CmdResult(cmdline='detect ' + args, describe="检测到改变", result_type=CMDRES_STR, result=table)

  def train(self, args="-1"):
      """分析通常的CAN包，如果索引为-1则指定所有缓冲区。

      :param str args: [缓冲区ID]

      :return: 分析结果
      :rtype: str
      """
      _index = int(args.strip())
      temp_buf = Replay()
      if _index == -1:
          # 如果_index = -1
          for buf in self.all_frames:
              temp_buf = temp_buf + buf['buf']
      else:
          temp_buf = self.all_frames[_index]['buf']

      # 如果之前存在分析的缓冲区则删除
      if self._train_buffer >= 0:
          del self.data_set[self._train_buffer]

      # 重新设置当前要分析的缓冲区索引,并更新数据字典
      self._train_buffer = _index
      self.data_set.update({_index: {}})

      self._last = 0
      self._full = len(temp_buf)

      # 如果当前模块的动作机制为开启，则开启
      if not self._action.is_set():
          self._action.set()
          self._need_status = True
          self._action.clear()

      #
      # 遍历指定的缓冲区，依次取出CAN包
      #
      for timestmp, can_msg in temp_buf:
          # 如果是CAN数据
          if can_msg.CANData:
              #
              # 如果当前的CANID不在数据字典中则添加一项
              # 这里是在对每个CANID建立一个索引
              #
              if can_msg.CANFrame.frame_id not in self.data_set[_index]:
                  self.data_set[_index][can_msg.CANFrame.frame_id] = {
                      'values_array': [can_msg.CANFrame.get_bits()],                      # 此ID对应的所有数据包
                      'count': 1,                                                         # 在此ID上发生包交换的次数
                      'changes': 0,                                                       # 在此ID上数据包发生改变的次数
                      'last': can_msg.CANFrame.get_bits(),                                # 在此ID上最后一个CAN包内容
                      'ch_last_time': round(timestmp, 4),                                 # 最后一次数据包内容改变的时间
                      'ch_max_time': 0,                                                   # 数据包改变发生的一个时间区间
                      'ch_min_time': 0,
                      'last_time': round(timestmp, 4),                                    # 最后一次接收数据包的时间
                      'min_time': 0,
                      'max_time': 0,
                      'change_bits': bitstring.BitArray('0b' + ('0' * 64), length=64)}    # 发生改变的位
              else:
                  # 如果当前CAN包的ID在数据字典里，则增加引用
                  self.data_set[_index][can_msg.CANFrame.frame_id]['count'] += 1
                  new_arr = can_msg.CANFrame.get_bits()
                  # 如果新包的内容与最后一个当前ID的包不一样
                  if new_arr != self.data_set[_index][can_msg.CANFrame.frame_id]['last']:
                      # 增加改变数量
                      self.data_set[_index][can_msg.CANFrame.frame_id]['changes'] += 1
                      # 将差异的位进行保存
                      self.data_set[_index][can_msg.CANFrame.frame_id]['change_bits'] |= (self.data_set[_index][can_msg.CANFrame.frame_id]['last'] ^ new_arr)
                      self.data_set[_index][can_msg.CANFrame.frame_id]['last'] = new_arr      # 更换最后一个包

                      # 如果发生两次内容的改变
                      if self.data_set[_index][can_msg.CANFrame.frame_id]['changes'] == 2:
                          # 更新一个两次间隔的时间
                          self.data_set[_index][can_msg.CANFrame.frame_id]['ch_max_time'] = round(timestmp - self.data_set[_index][can_msg.CANFrame.frame_id]['ch_last_time'] + 0.001, 4)
                          self.data_set[_index][can_msg.CANFrame.frame_id]['ch_min_time'] = round(timestmp - self.data_set[_index][can_msg.CANFrame.frame_id]['ch_last_time'] - 0.001, 4)

                      # 如果改变发生两次以上，直接使用线性时间
                      if self.data_set[_index][can_msg.CANFrame.frame_id]['changes'] > 2:
                          ch_time = round(timestmp - self.data_set[_index][can_msg.CANFrame.frame_id]['ch_last_time'], 4)
                          if ch_time > self.data_set[_index][can_msg.CANFrame.frame_id]['ch_max_time']:
                              self.data_set[_index][can_msg.CANFrame.frame_id]['ch_max_time'] = ch_time
                          elif ch_time < self.data_set[_index][can_msg.CANFrame.frame_id]['ch_min_time']:
                              self.data_set[_index][can_msg.CANFrame.frame_id]['ch_min_time'] = ch_time

                      # 更新最后一次改变的时间
                      self.data_set[_index][can_msg.CANFrame.frame_id]['ch_last_time'] = round(timestmp, 4)

                  if self.data_set[_index][can_msg.CANFrame.frame_id]['count'] == 2:
                      self.data_set[_index][can_msg.CANFrame.frame_id]['max_time'] = round(timestmp - self.data_set[_index][can_msg.CANFrame.frame_id]['last_time'] + 0.001, 4)
                      self.data_set[_index][can_msg.CANFrame.frame_id]['min_time'] = round(timestmp - self.data_set[_index][can_msg.CANFrame.frame_id]['last_time'] - 0.001, 4)

                  if self.data_set[_index][can_msg.CANFrame.frame_id]['count'] > 2:
                      ch_time = round(timestmp - self.data_set[_index][can_msg.CANFrame.frame_id]['last_time'], 4)
                      if ch_time > self.data_set[_index][can_msg.CANFrame.frame_id]['max_time']:
                          self.data_set[_index][can_msg.CANFrame.frame_id]['max_time'] = ch_time
                      elif ch_time < self.data_set[_index][can_msg.CANFrame.frame_id]['min_time']:
                          self.data_set[_index][can_msg.CANFrame.frame_id]['min_time'] = ch_time

                  self.data_set[_index][can_msg.CANFrame.frame_id]['last_time'] = round(timestmp, 4)

              # 更新动作
              if not self._action.is_set():
                  self._action.set()
                  self._last += 1
                  self._action.clear()

      time.sleep(1)
      if not self._action.is_set():
          self._action.set()
          self._need_status = False
          self._action.clear()
      #summy = 'Profiling finished: {} uniq. arb. ID'.format(len(self.data_set[_index]))
      summy = "统计完成: 检测到 {} 个'CANID'".format(len(self.data_set[_index]))
      return CmdResult(cmdline='statistic ' + args, describe=summy, result_type=CMDRES_OBJ, result=self.data_set[_index])

  def find_ab(self, _index):
      """
      在当前流量中通过已经学习到的知识，来寻找差异包(此命令需要在之前使用'train'来学习其他缓冲)。

      hypothesis [缓冲区索引]
      """
      _index = int(_index.strip())

      if self._train_buffer < 0:
          return CmdResult(cmdline='hypothesis ' + str(_index), describe="统计表索引小于0", last_error=-2)
      elif self._train_buffer == _index:
          return CmdResult(cmdline='hypothesis ' + str(_index), describe="统计表索引等于指定缓存区索引", last_error=-2)
      if _index > self._index:
          return CmdResult(cmdline='hypothesis ' + str(_index), describe="指定缓存区索引大于当前缓冲区索引", last_error=-2)

      temp_buf = self.all_frames[_index]['buf']

      self.data_set.update({_index: {}})

      correlator_changes = []
      known_changes = []
      self.history = []
      self._last = 0
      self._full = len(temp_buf) * 2

      # 线程同步
      if not self._action.is_set():
                  self._action.set()
                  self._need_status = True
                  self._action.clear()
      # 遍历缓冲区
      for timestmp, can_msg in temp_buf:
          if can_msg.CANData:
              # 如果是CAN包并且CANID不在数据字典里则添加一项
              if can_msg.CANFrame.frame_id not in self.data_set[_index]:

                  self.data_set[_index][can_msg.CANFrame.frame_id] = {
                      'count': 1,                                                 # 当前ID被发生包交换的次数
                      'changes': 0,                                               # CAN包发生改变的次数
                      'last': can_msg.CANFrame.get_bits(),                        # 最后一个CAN包的内容
                      'last_time': round(timestmp, 4),                            # 最后一次接收的时间
                      'ch_last_time': round(timestmp, 4),                         # 最后一次发生改变的时间
                      'diff': bitstring.BitArray('0b' + '0' * 64, length=64),     # 变换包的不同
                      'history': [],                                              # 历史记录
                      'curr_comm': 0,                                             # 当前注释索引
                      'comm': []                                                  # 注释
                  }
              else:
                  #
                  # 这里如果此CANID在数据字典中
                  #
                  self.data_set[_index][can_msg.CANFrame.frame_id]['count'] += 1

                  # new_arr中保存了当前包的2进制位
                  new_arr = can_msg.CANFrame.get_bits()
                  
                  #
                  # 获取当前CANID的变化状态
                  # changed : 表示当前数据包与上一次的'值'不同
                  # released : 表示当前的变化又改变到原先的值
                  # changed_same : 两次发包数据相同
                  # changed_1 : 表示再次改变,无论是值还是位置都在已知的变化当中
                  #
                  chg = self.data_set[_index][can_msg.CANFrame.frame_id].get('changed', False)
                  xchg = self.data_set[_index][can_msg.CANFrame.frame_id].get('released', False)
                  schg = self.data_set[_index][can_msg.CANFrame.frame_id].get('changed_same', False)
                  nchg = self.data_set[_index][can_msg.CANFrame.frame_id].get('changed_1', False)
                  
                  #
                  # 如果与最后一次的CAN包内容不一样发生差异
                  #
                  if new_arr != self.data_set[_index][can_msg.CANFrame.frame_id]['last']:
                      # 增加变化引用
                      self.data_set[_index][can_msg.CANFrame.frame_id]['changes'] += 1

                      # 与上一次比较，找出是那些位发生了改变
                      diff = new_arr ^ self.data_set[_index][can_msg.CANFrame.frame_id]['last']

                      # 读取上一次改变的位数
                      orig = self.data_set[self._train_buffer].get(can_msg.CANFrame.frame_id, {})
                      orig_bits = orig.get('change_bits', bitstring.BitArray('0b' + '0' * 64, length=64))

                      #
                      # 判断上次改变的位置与初始化(统计包的数据)改变的位置不一致
                      # 表示只在这次中出现的包
                      #
                      # 这里只要当前的CAN包不在初始变化位置范围内，则进入到异常包中，在这些包中但凡与背景变化不一致
                      # 则提取出来
                      #
                      if (diff | orig_bits) != orig_bits:

                          #
                          # 值不同，变化位置不同，则认为是一个新的改变
                          #
                          if not chg and not schg and not nchg:
                              #
                              # 标记变化位置不同，是一个新的位置改变
                              # 这里将changed_same 设置为False 表示这是一个新的改变
                              # 
                              self.data_set[_index][can_msg.CANFrame.frame_id]['changed_same'] = False
                              ev = " 第一次改变 (新的位置变化), 上一条数据: " + str(self.data_set[_index][can_msg.CANFrame.frame_id]['last'].hex)

                              #
                              # 如果此条变化具有相关因子则将相关因子合并输出到打印结果中
                              # 并且添加注释说明
                              #
                              if len(correlator_changes) > 0:
                                  ev = " " + str([hex(cor) for cor in correlator_changes]) + ev
                                  # 如果当前的CANID不再分析历史记录中，则添加
                                  if can_msg.CANFrame.frame_id not in self.history:
                                      self.history.append(can_msg.CANFrame.frame_id)
                                  self.history = list(set(self.history).union(correlator_changes))
                                  # 添加注释,发生第一次改变
                                  self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" 第一次改变, 上一条数据: " + str(self.data_set[_index][can_msg.CANFrame.frame_id]['last'].hex) + ", 引起改变的原因可能是因为之前的下一个事件: " + str([hex(cor) for cor in correlator_changes]))
                              else:
                                  # 相关因子无变化，但是发生改变
                                  self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" 第一次改变, 上一条数据: " + str(self.data_set[_index][can_msg.CANFrame.frame_id]['last'].hex))
                              
                              #
                              # 如果当前发生的改变，不在已知列表里(之前发生过改变的位置)
                              # 使用(CANID,与之前的对比位置)
                              # !!!这里使用了当前的CANID加入到相关因子中了，其意义是由于自身改变，引起了当前CANID其他数据位的改变
                              # 但是也可能是数值进位引起的变化
                              #
                              # 将(CANID,与之前的对比位置)进行在已知的变化中查找的意义，是想说明是因为上一次这个CANID的这个变化可能引起
                              # 包的变化。
                              # 这个并不是一个很准确的说明
                              #
                              # 之前没有发生过改变，但是这次发生了改变，变化的位置又没有见过则将当前CANID添加到关联CANID中
                              #
                              if (can_msg.CANFrame.frame_id, self.data_set[_index][can_msg.CANFrame.frame_id]['diff']) not in known_changes:
                                  correlator_changes.append(can_msg.CANFrame.frame_id)

                              # 更新数据字典，这里更新了所有变化标记，并且这里更新了diff字段，记录了所有历史上经过变化的位
                              # diff | self.data_set[_index][can_msg.CANFrame.frame_id]['diff'] 记录数据位的所有变化
                              self.data_set[_index][can_msg.CANFrame.frame_id].update({'changed': True, 'released': False, 'changed_1': False, 'diff': diff | self.data_set[_index][can_msg.CANFrame.frame_id]['diff']})

                          #
                          # 此次发生的变化位置与上一次相同，只是内容不同
                          # 这里使用在data_set中的'diff'位来判断与上次变化是否相同
                          # data_set中的'diff'与chg,schg,nchg是指的上次与上上次的变化
                          # diff是位比较,那么说明值相同
                          #
                          # 这里使用了 diff == data_set['diff']，但是data_set['diff']是上几次变化的统计，这里可能会存在显示不准
                          # 只能显示类似: 0001 -> 0002 -> 0001 这种，但是不能记录 0001 -> 0002 -> 0003-> 0001,这种
                          #
                          elif (chg or schg or nchg) and diff == self.data_set[_index][can_msg.CANFrame.frame_id]['diff']:
                              #ev = " RELEASED to original value "
                              ev = " 还原到原始的值 "
                              self.data_set[_index][can_msg.CANFrame.frame_id]['released'] = True
                              self.data_set[_index][can_msg.CANFrame.frame_id]['changed'] = False
                              self.data_set[_index][can_msg.CANFrame.frame_id]['changed_1'] = False
                              self.data_set[_index][can_msg.CANFrame.frame_id]['changed_same'] = False

                              #
                              # 如果当前的CANID在相关因子中则删除，并将变化添加到已知变化中
                              # 这里的算法是这样的，如果此CANID的数据包变化又还原回去了，说明数值是在一个
                              # 范围内的，则我们不再相关因子中去关注它。因为并不是由于它的变化引起其他位的变化
                              #
                              if can_msg.CANFrame.frame_id in correlator_changes:
                                  correlator_changes.remove(can_msg.CANFrame.frame_id)
                                  # 将统计缓存中的变化记录到当前已知列表中
                                  known_changes.append((can_msg.CANFrame.frame_id, self.data_set[_index][can_msg.CANFrame.frame_id]['diff']))
                              #self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" released value back ")
                              self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" 返回到之前的值 ")
                          
                          #
                          # 如果这次的变化与上次不同,无论是值改变还是位置改变
                          # 都属于'再次改变'
                          #
                          else:
                              #ev = " CHANGED AGAIN "
                              ev = " 再次改变 "

                              # 记录所有的相关因子
                              if len(correlator_changes) > 0:
                                  ev = " " + str([hex(cor) for cor in correlator_changes]) + ev
                                  # 将当前CANID添加到历史记录中
                                  if can_msg.CANFrame.frame_id not in self.history:
                                      self.history.append(can_msg.CANFrame.frame_id)
                                  self.history = list(set(self.history).union(correlator_changes))
                                  #self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" additional changes, probably because of: " + str([hex(cor) for cor in correlator_changes]))
                                  self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" 额外的改变, 改变的原因可能是: " + str([hex(cor) for cor in correlator_changes]))

                              # 如果当前CANID在关联因子中则将其删除并记录变化
                              if can_msg.CANFrame.frame_id in correlator_changes:
                                  correlator_changes.remove(can_msg.CANFrame.frame_id)
                                  known_changes.append((can_msg.CANFrame.frame_id, self.data_set[_index][can_msg.CANFrame.frame_id]['diff']))

                              # 如果当前CANID是拥有一个在当前对比中从未出现过的位置，则也添加到关联因子中
                              if (can_msg.CANFrame.frame_id, self.data_set[_index][can_msg.CANFrame.frame_id]['diff'] | diff) not in known_changes:
                                  correlator_changes.append(can_msg.CANFrame.frame_id)

                              self.data_set[_index][can_msg.CANFrame.frame_id].update({'diff': (self.data_set[_index][can_msg.CANFrame.frame_id]['diff'] | diff)})
                              self.data_set[_index][can_msg.CANFrame.frame_id]['changed_1'] = True
                              self.data_set[_index][can_msg.CANFrame.frame_id]['changed'] = False
                              self.data_set[_index][can_msg.CANFrame.frame_id]['changed_same'] = False
                          #
                          # 合成一条打印消息
                          #
                          msgs = self.data_set[_index][can_msg.CANFrame.frame_id].get('breaking_messages', [])
                          msgs.append("#" + str(self.data_set[_index][can_msg.CANFrame.frame_id]['count']) + " [" + str(round(timestmp, 4)) + "] " + can_msg.CANFrame.get_text() + ev)
                          self.dump_stat.append_time(timestmp, can_msg)
                          self.data_set[_index][can_msg.CANFrame.frame_id].update({'breaking_messages': msgs})

                  #
                  # 与最后一次包相同
                  #
                  elif self.data_set[_index][can_msg.CANFrame.frame_id].get('changed', False):
                      self.data_set[_index][can_msg.CANFrame.frame_id]['changed'] = False
                      self.data_set[_index][can_msg.CANFrame.frame_id]['changed_same'] = True
                      # 发生变化从相关因子列表中删除
                      if can_msg.CANFrame.frame_id in correlator_changes:
                          correlator_changes.remove(can_msg.CANFrame.frame_id)
                          known_changes.append((can_msg.CANFrame.frame_id, self.data_set[_index][can_msg.CANFrame.frame_id]['diff']))
                  #
                  # 与上一次值不同，但是没有新的位置变化
                  #
                  elif self.data_set[_index][can_msg.CANFrame.frame_id].get('changed_1', False):
                      self.data_set[_index][can_msg.CANFrame.frame_id]['changed_1'] = False
                      self.data_set[_index][can_msg.CANFrame.frame_id]['changed_same'] = True
                      # 发生变化从相关因子列表中删除
                      if can_msg.CANFrame.frame_id in correlator_changes:
                          correlator_changes.remove(can_msg.CANFrame.frame_id)
                          known_changes.append((can_msg.CANFrame.frame_id, self.data_set[_index][can_msg.CANFrame.frame_id]['diff']))
                  
                  #
                  # 更新最后一次变化
                  #
                  chg = self.data_set[_index][can_msg.CANFrame.frame_id].get('changed', False)
                  xchg = self.data_set[_index][can_msg.CANFrame.frame_id].get('released', False)
                  schg = self.data_set[_index][can_msg.CANFrame.frame_id].get('changed_same', False)
                  nchg = self.data_set[_index][can_msg.CANFrame.frame_id].get('changed_1', False)

                  self.data_set[_index][can_msg.CANFrame.frame_id]['last'] = new_arr
                  self.data_set[_index][can_msg.CANFrame.frame_id]['ch_last_time'] = round(timestmp, 4)

                  #
                  # 如果当前CANID的包有两个以上，这里与统计信息做比较
                  #
                  if self.data_set[_index][can_msg.CANFrame.frame_id]['count'] > 2:
                      orig = self.data_set[self._train_buffer].get(can_msg.CANFrame.frame_id, None)
                      error_rate = 0.04
                      if orig:
                          orig_max_time = orig.get('max_time', None)
                          orig_min_time = orig.get('min_time', None)
                          # 得到当前两个包发送的间隔
                          curr_ch_time = round(timestmp - self.data_set[_index][can_msg.CANFrame.frame_id]['last_time'], 4)
                          # 与统计信息对比时间
                          if orig_max_time is not None and orig_min_time is not None:
                              # 如果当前的两个包的时间间隔与统计包的速率相差太远
                              if curr_ch_time < (orig_min_time - error_rate):
                                  #ev = " 'impulse' rate increased,  delay: " + str(curr_ch_time) + " orig: " + str(orig_min_time)
                                  ev = " '脉冲' 速率增加, 延迟: " + str(curr_ch_time) + " 原始值: " + str(orig_min_time)
                                  
                                  #
                                  # 相同的改变
                                  #
                                  if schg:
                                      #ev = " EVENT CONTINUED " + ev
                                      #self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" 'impulse' rate increased abnormally: EVENT")
                                      ev = " 事件 连续 " + ev
                                      self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" '脉冲' 速率增加异常: 事件")
                                  #
                                  # 再次改变
                                  #
                                  elif nchg:
                                      #ev = " EVENT NEXT STAGE" + ev
                                      #self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" 'impulse' rate increased abnormally: NEW STAGE")
                                      ev = " 事件 下一个阶段" + ev
                                      self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" '脉冲' 速率增加异常: 新的阶段")
                                  
                                  #
                                  # 还原到原始的值
                                  #
                                  elif xchg:
                                      #ev = " EVENT FINISHED " + ev
                                      #self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" 'impulse' rate increased abnormally: EVENT FINISHED")
                                      ev = " 事件 已完成 " + ev
                                      self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" '脉冲' 速率增加异常: 事件 已完成")
                                  
                                  #
                                  # 没有改变
                                  #
                                  elif not chg:
                                      #self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" 'impulse' rate increased abnormally...")
                                      self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" '脉冲' 速率增加异常...")
                                  
                                  #
                                  # 如果什么都没有发生改变,这里可能schg为True
                                  # 某个包一直以极快的平率发送相同的数据，也属于异常，这里也找出来
                                  #
                                  if not chg and not nchg and not xchg:
                                      msgs = self.data_set[_index][can_msg.CANFrame.frame_id].get('breaking_messages', [])
                                      msgs.append("\t#" + str(self.data_set[_index][can_msg.CANFrame.frame_id]['count']) + " [" + str(round(timestmp, 4)) + "] " + can_msg.CANFrame.get_text() + ev)
                                      self.dump_stat.append_time(timestmp, can_msg)
                                      self.data_set[_index][can_msg.CANFrame.frame_id].update({'breaking_messages': msgs})
                  # 更新最后一次时间
                  self.data_set[_index][can_msg.CANFrame.frame_id]['last_time'] = round(timestmp, 4)

              #
              # 如果当前的CANID在统计包中没有出现
              # 则添加到关联因子中
              #
              if can_msg.CANFrame.frame_id not in self.data_set[self._train_buffer]:
                  correlator_changes.append(can_msg.CANFrame.frame_id)
                  #self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" New arb. ID ")
                  self.data_set[_index][can_msg.CANFrame.frame_id]['comm'].append(" 新的'CANID' ")
                  msgs = self.data_set[_index][can_msg.CANFrame.frame_id].get('breaking_id_messages', [])
                  #msgs.append("#" + str(self.data_set[_index][can_msg.CANFrame.frame_id]['count']) + " [" + str(round(timestmp, 4)) + "] " + can_msg.CANFrame.get_text() + " NEW Arb. ID")
                  msgs.append("#" + str(self.data_set[_index][can_msg.CANFrame.frame_id]['count']) + " [" + str(round(timestmp, 4)) + "] " + can_msg.CANFrame.get_text() + " 新的'CANID'")
                  # 记录到dump_stat变量中
                  self.dump_stat.append_time(timestmp, can_msg)
                  self.data_set[_index][can_msg.CANFrame.frame_id].update({'breaking_messages': msgs})

              if not self._action.is_set():
                  self._action.set()
                  self._last += 1
                  self._action.clear()

      # 列出所有异常的ID
      #result = " Profiling comparison results (abnormalities by ID):\n\n"
      result = " 对比结果完成 (通过'CANID'进行异常对比):\n\n"

      for aid, body in self.data_set[_index].items():
          # New devices
          msgs = body.get('breaking_messages', [])
          if len(msgs) > 0:
              # 这里就是列出所有做过 关联因子的CANID
              if aid in self.history:
                  #result += "\t" + hex(aid) + " - found abnormalities:\n"
                  result += "\t" + hex(aid) + " - 已发现异常:\n"
                  for msg in msgs:
                      result += "\t\t" + msg + "\n"
              else:
                  self.dump_stat.remove_by_id(aid)
          if not self._action.is_set():
              self._action.set()
              self._last += body['count']
              self._action.clear()

      #result2 = "\n\nSELECTED SESSION(ready to dump into file now and for ACTIVE check)::\n\n"
      rows = [['TIME', 'ID', 'LENGTH', 'MESSAGE', 'COMMENT']]
      result2 = "\n\nSELECTED SESSION(目前已经保存到文件并且激活'hypothesis'功能)::\n\n"
      for (tms, can_msg) in self.dump_stat._stream:
          if can_msg.CANData:
              if len(self.data_set[_index][can_msg.CANFrame.frame_id]['comm']) > 0:
                  comment = self.data_set[_index][can_msg.CANFrame.frame_id]['comm'][self.data_set[_index][can_msg.CANFrame.frame_id]['curr_comm'] % len(self.data_set[_index][can_msg.CANFrame.frame_id]['comm'])]
              else:
                  comment = " hz "
              self.data_set[_index][can_msg.CANFrame.frame_id]['curr_comm'] += 1
              rows.append([str(round(tms, 4)), hex(can_msg.CANFrame.frame_id), str(can_msg.CANFrame.frame_length), self.get_hex(can_msg.CANFrame.frame_raw_data), comment])

      cols = list(zip(*rows))
      col_widths = [max(len(value) for value in col) for col in cols]
      format_table = '    '.join(['%%-%ds' % width for width in col_widths])
      for row in rows:
          result2 += format_table % tuple(row) + "\n"
      result2 += "\n"

      # 这里更新假设信息缓冲区用作检验支撑
      self._rep_index = _index
      self.commands['test'].is_enabled = True
      self.commands['dumps'].is_enabled = True

      if not self._action.is_set():
          self._action.set()
          self._need_status = False
          self._action.clear()

      ret = result2 + result
      return CmdResult(cmdline='hypothesis ' + str(_index), describe="假设问题", result_type=CMDRES_STR, result=ret)

  def dump_ab(self, filename):
      """
      在当前流量中探索异常包并保存到回访文件

      dumps <文件名>
      """
      ret = self.dump_stat.save_dump(filename.strip())
      return CmdResult(cmdline='dumps ' + filename, describe="假设问题保存", result_type=CMDRES_STR, result=ret)

  def act_detect(self):
      """
      在dump_stat包中验证。在dump_stat包中的数据符合以下三种
      1. 在统计包中没有出现的CANID
      2. 某个CANID的数据包发生过新的变化(位置)
      3. 某个CANID的数据包在以极快的速率发送数据相同的数据包
      """
      curr = 0
      weigths = {"Not found": 0}
      
      # 开启动作验证
      self._active_check = True
      if self._active:

          #
          # 验证dump_stat包是否为空并且遍历
          #
          last = len(self.dump_stat)
          if last > 0:
              # 得到最后一个包
              (last_time, last_frame) = self.dump_stat.get_message(last - 1)
              # 遍历所有的异常包
              while curr < last - 1:
                  # 获取一条记录
                  (timeo, test_frame) = self.dump_stat.get_message(curr)
                  # 计算等待时间
                  waiting_time = last_time - timeo + 1
                  curr += 1

                  # 判断消息是否为空
                  if test_frame:
                      key = test_frame.get_text()
                      idg = test_frame.frame_id
                      # 生成新的缓存
                      self.new_diff("STAT_CHECK_ACT_" + key)
                      self.info(" 发送测试数据帧: " + key)
                      # 建立当前包的权重值
                      tmp_w = weigths.get(key, 0)

                      # 将数据写入到发送队列中，这里是一个安全线程操作
                      while self._action.is_set():
                          time.sleep(0.01)
                      self._action.set()
                      self._stat_resend = test_frame
                      self._action.clear()

                      #
                      # 这里循环等待将发送队列中的测试数据发送出去
                      #
                      while 1:
                          time.sleep(1)
                          if not self._action.is_set():
                              self._action.set()
                              if self._stat_resend is None:
                                  self._action.clear()
                                  self.info(" 测试数据帧已发送完毕: " + test_frame.get_text())
                                  time.sleep(waiting_time)
                                  break
                              self._action.clear()
                      self.info(" 检测改变... ")
                      self._active = False

                      #
                      # 发送完毕
                      # 遍历所有曾出现过的CANID
                      #
                      for idf in self.history:
                          #
                          # 在当前新的缓冲区内(回馈内容)搜索CANID
                          # 将搜索的结果全部换成16进制字符串并保存到一个队列
                          #
                          buf1 = self.all_frames[-1]['buf'].search_messages_by_id(idf)
                          buf1x = [bitstring.BitArray((b'\x00' * (8 - len(x))) + x) for x in buf1]

                          #
                          # 如果此ID在统计包中，则取出在统计包中的变化情况
                          # 没有则初始化一个位置队列
                          #
                          if idf in self.data_set[self._train_buffer]:
                              orig_bits = self.data_set[self._train_buffer][idf]['change_bits']
                          else:
                              orig_bits = bitstring.BitArray(b'\x00' * 8)

                          #
                          # 如果测试的CANID与检验的CANID不相同，则开始对比
                          # 这里是一个快速对比算法，找出初始位置与假设统计中的位置的不同
                          #
                          if idg != idf:
                              #
                              # 使用初始对比位置信息与假设数据包中位置信息做对比，找出差异位置
                              # 在假设包中的位置diff信息，是所有变化过的位置,而初始位置与假设包的位置做差异
                              # looking_bits中保存的就是在初始位置与假设包中分别出现的位置
                              # 这里主要是取出假设包与初始位置的变化。那么在发送完测试数据后，反馈数据的变化
                              # 也一定在这个范围内。那么我们就统计落在这个范围内的计数。
                              #
                              looking_bits = orig_bits ^ self.data_set[self._rep_index][idf]['diff']
                              self.info("对比位值 (" + hex(idf) + "): " + looking_bits.bin)

                              last_b = orig_bits
                              chg_b = bitstring.BitArray(b'\x00' * 8)
                              itr = 0
                              
                              #
                              # 如果接收到缓冲数据不为空
                              #
                              if len(buf1x) > 1:
                                  # 遍历所有包
                                  for bit in buf1x:
                                      #
                                      # 找出当前的数据与上一个包的差异
                                      # 并记录到chg_b中，这里保存了所有不一样的唯一变化位置
                                      #
                                      chg_b |= bit ^ last_b
                                      last_b = bit            # 更新最后一个位置
                                      itr += 1
                                      #
                                      # 如果在当前变化的是落在这个差异范围内的则使得引用次数+1
                                      #
                                      self.info("\n比较位数据 " + bit.bin + " 与 " + (looking_bits & chg_b).bin)
                                      if (looking_bits & chg_b).int != 0 and itr > 1:
                                          self.info("已匹配")
                                          tmp_w += 1
                      #
                      # 这里应该有个对应，发送了测试数据与哪个CANID关联的最紧密
                      # 更新一个测试数据的权重
                      #
                      weigths[key] = tmp_w
                      self._active = True
              self.info("返回对比权重: " + str(weigths))
              self._active_check = False
              ret = str(max(weigths.keys(), key=(lambda k: weigths[k])))
              return CmdResult(cmdline='test', describe="反馈事件已发生", result_type=CMDRES_STR, result=ret)
          else:
              self._active_check = False
              return CmdResult(cmdline='test', describe="未找到状态检测缓存，请使用'hypothesis'命令生成状态缓存")
      else:
          self._active_check = False
          return CmdResult(cmdline='test', describe="模块未激活", last_error=-2)

  def load_rep(self, files):
      """
      从文件加载回访数据到缓冲区

      load <文件名1> [,文件名2,...]
      """
      _files = [fl.strip() for fl in files.split(',')]
      ret = "加载缓冲区:\n"
      for fl in _files:
          self.new_diff(fl + "_buffer")
          self.all_frames[-1]['buf'].parse_file(fl, self._bus)
          ret += "\t" + fl + ", 缓冲区索引: " + str(len(self.all_frames) - 1) + " : " + str(len(self.all_frames[-1]['buf'].stream)) + " 数据帧\n"
      return CmdResult(cmdline='load ' + files, describe="加载缓存文件", result_type=CMDRES_STR, result=ret)

  def do_start(self, params):
      if len(self.all_frames[-1]['buf'].stream) == 0:
          self.all_frames[-1]['buf'].add_timestamp()
