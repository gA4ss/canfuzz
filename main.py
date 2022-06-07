#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import re
import ast
import cmd
import sys
import traceback

from frame.kernel.engine import L6Engine
from frame.stream.cmdres import CmdResult, CMDRES_ERROR, CMDRES_NULL, CMDRES_INT, CMDRES_STR, CMDRES_TAB, CMDRES_OBJ

class FrameCLI(cmd.Cmd):
  def __init__(self, l6engine, *args, **kwargs):
    self.l6engine = l6engine
    self.intro = '使用 help 或者 ? 列出所有命令.\n'
    self.prompt = '# '
    super(FrameCLI, self).__init__(*args, **kwargs)

  def do_start(self, arg):
    """开启L6引擎。
    """
    self.l6engine.start_loop()

  def do_stop(self, arg):
    """停止L6引擎。
    """
    self.l6engine.stop_loop()

  def do_view(self, arg):
    """浏览当前策略流程。
    """
    actions = self.l6engine.actions
    print('加载所有动作队列 ({}):'.format(len(actions)), end='\n' * 2)
    # Generate table rows
    table = [
      ['({})'.format(i), name, str(params), str(module.is_active)]
      for i, (name, module, params) in enumerate(actions)]
    # Create printing format with correct max padding.
    sizes = [10] * 4  # Padding 10 characters minimum.
    for row in table:
      # Get max(len(cell), padding) for each cell in each row of the table
      sizes = list(map(max, zip(map(len, row), sizes)))
    row_format = ''.join('{{:{}}}'.format(size + 4) for size in sizes)

    print(row_format.format(*('索引号', '模块', '参数', '是否激活')))
    # print(row_format.format(*('ID', 'Module', 'Parameters', 'Active')))
    print('-' * (sum(sizes) + 2 * len(sizes)))
    if len(table):
      for row in table[:-1]:
        print(row_format.format(*row))
        print(row_format.format(*('', '||', '', '', '')))
        print(row_format.format(*('', '||', '', '', '')))
        print(row_format.format(*('', '\/', '', '', '')))
      print(row_format.format(*table[-1]), end='\n' * 2)

  def do_edit(self, arg):
    """编辑模块动作参数。

    edit <模块ID> <字典配置>

    例如:
        edit 0 {'action': 'write', 'pipe': 'Cabin'}
    """
    match = re.match(r'(\d+)\s+(.+)', arg, re.IGNORECASE)
    if not match:
      print('丢失/无效的参数. 参见: help edit')
      return
    module = int(match.group(1).strip())
    _paramz = match.group(2).strip()
    try:
      paramz = ast.literal_eval(_paramz)
      self.l6engine.edit_module(module, paramz)
    except Exception:
      print('编辑模块参数发生错误 {}:'.format(arg))
      traceback.print_exc()
      return
    print('编辑模块 {}'.format(self.l6engine.actions[module][0]))
    print('添加参数: {}'.format(self.l6engine.actions[module][2]))

    active = self.l6engine.actions[module][1].is_active
    if active:
      self.l6engine.actions[module][1].do_activate(0, 0)
    if self.l6engine.status_loop:
      self.l6engine.actions[module][1].do_stop(paramz)
      self.l6engine.actions[module][1].do_start(paramz)
    if active:
      self.l6engine.actions[module][1].do_activate(0, 1)

  def do_cmd(self, arg):
    """调用模块命令。

    cmd <模块ID> <命令>

    例子:
        cmd 0 S
    """
    match = re.match(r'(\d+)\s+(.*)', arg, re.IGNORECASE)
    if not match:
      print('丢失/无效的参数. 参见: help cmd')
      return
    _mod = int(match.group(1).strip())
    _paramz = match.group(2).strip()
    text = ""
    try:
      cmdres = self.l6engine.call_module(_mod, str(_paramz))
      if cmdres == None:
        text = "调用命令错误!"
      else:
        if cmdres.result_type is not None:
          if cmdres.result_type == CMDRES_STR:
            text = cmdres.result
          elif cmdres.result_type == CMDRES_INT:
            text = str(cmdres.result)
          else:
            text = ""
    except Exception:
      print('调用命令发生错误 {}:'.format(arg))
      traceback.print_exc()
      return
    if cmdres is not None:
      print('描述: {}'.format(cmdres.describe))
    if len(text) != 0:
      print('回应: {}'.format(text))

  def do_help(self, arg):
    """显示帮助。

    help [模块ID]
    """
    match = re.match(r'(\d+)', arg, re.IGNORECASE)
    if not match:
      super(FrameCLI, self).do_help(arg)
      return
    module = int(match.group(1).strip())
    try:
      mod = self.l6engine.actions[module][1]
    except Exception:
      print('无效的指令: ')
      traceback.print_exc()
      return
    print('模块 {}: {}\n{}\n命令:'.format(mod.__class__.__name__, mod.name, mod.help))
    for key, value in mod.commands.items():
      print('\t{} {} - {}'.format(key, value.desc_params, value.description))
    print()

  def do_quit(self, arg):
    """退出CANFUZZ。
    """
    print('退出中，请等待... ', end='')
    self.l6engine.stop_loop()
    self.l6engine.engine_exit()
    print('完成')
    raise SystemExit

def run_canfuzz():
  can_engine = L6Engine()
  modules = can_engine.list_modules()
  print('List of available modules (total {}):'.format(len(modules)))
  for name, info in modules.items():
     description, path = info
     print('\t{:20} - {} (from: {})'.format(name, description, path))

  #
  # 这里判断命令行
  #
  if len(sys.argv) >= 2:
    can_engine.load_config(sys.argv[1])

  # run command line
  prompt = FrameCLI(can_engine)
  prompt.cmdloop()

if __name__ == '__main__':
  run_canfuzz()