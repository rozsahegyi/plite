# coding=utf-8

import sys, os, time, itertools
from collections import defaultdict
from functools import partial
sys.path.append(os.path.realpath(os.path.curdir + '\\Lib\\site-packages'))
import wx, wx.lib.newevent


class App(wx.App):
	def __init__(self, plite, **config):
		for k, v in config.iteritems(): setattr(self, k, v)
		self.hosts = [{'url': x, 'check': False} for x in self.hosts]
		self.running = False
		self.UpdateEvent, self.EVT_UPDATE = wx.lib.newevent.NewEvent()
		super(App, self).__init__(False)

	def OnInit(self):
		self.frame = wx.Frame(None, wx.ID_ANY, 'Plite 1.0')#, style=wx.FRAME_NO_TASKBAR)
		self.tb = wx.TaskBarIcon()
		self.tb.frame = self.frame

		self.Bind(wx.EVT_SET_FOCUS, self.FrameFocus)
		self.frame.Bind(wx.EVT_SET_FOCUS, self.FrameFocus)
		self.frame.Bind(wx.EVT_CLOSE, self.OnClose)
		self.tb.Bind(wx.EVT_SET_FOCUS, self.TaskBarFocus)
		self.tb.Bind(wx.EVT_TASKBAR_LEFT_DCLICK, self.OnClose)
		self.tb.Bind(wx.EVT_TASKBAR_LEFT_DOWN, self.TaskBarMenu)
		self.tb.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.TaskBarMenu)
		self.tb.Bind(self.EVT_UPDATE, self.update)

		self.setup_menu()
		self.set_scale(None, option=1)
		self.set_rate(None, option=0)
		self.set_slice(None, option=2)
		for host in self.hosts: self.toggle_host(None, host=host['url'])
		self.running = True
		return True

	def update_event(self, data):
		wx.PostEvent(self.tb, self.UpdateEvent(data=data))

	def update(self, event):
		if not event.data: return
		icon = wx.EmptyIcon()
		icon.CopyFromBitmap(wx.BitmapFromBuffer(self.icon_size, self.icon_size, event.data))
		if self.tb: self.tb.SetIcon(icon, '%d ms' % -100) # make sure the taskbar still exists
		# self.tb.SetIcon(wx.Icon('icons/favicon.ico', wx.BITMAP_TYPE_ICO))

	def setup_menu(self):
		# methods to generate various menu items
		time_format = lambda sec: '%d seconds' % sec if sec < 60 else '%.2g minutes' % (sec / 60)
		methods = {
			'separator': lambda a: [[None]],
			'normal': lambda a: [[a[0], len(a) > 1 and a[1] or wx.ITEM_NORMAL] + a[2:]],
			'scale_options': lambda a: [['%g ms' % x, wx.ITEM_RADIO, 'set_scale', i, x] for i, x in enumerate(a[1:])],
			'rate_options': lambda a: [['%g sec' % x, wx.ITEM_RADIO, 'set_rate', i, x] for i, x in enumerate(a[1:])],
			'slice_options': lambda a: [[time_format(x), wx.ITEM_RADIO, 'set_slice', i, x] for i, x in enumerate(a[1:])],
			'hosts': lambda a: [[x['url'], wx.ITEM_CHECK, 'toggle_host', i] for i, x in enumerate(self.hosts)],
		}

		def transform(item):
			# store any untransformed list of values -- TODO: purify this!
			if item and item[1:]: setattr(self, item[0], item[1:])
			method = 'separator' if not item or not item[0] else 'normal' if item[0] not in methods else item[0]
			return methods[method](item)

		# generate menu items, flatten the nested list
		menu = [item for sub in map(transform, self.menu) for item in sub]

		# here menu is a list of: ['name', item_kind, callback, callback_args]
		# map each option with their respective index (so we can set "scale option #2")
		self.menu = wx.Menu()
		self.option_ids = defaultdict(dict)
		for i, item in enumerate(menu):
			menu[i] = item = [wx.NewId()] + item if item[0] else [wx.ID_SEPARATOR]
			if len(item) > 4:
				func, option = item[3:5]
				self.option_ids[func][option] = item[0]
			if len(item) > 1: item = (item[0], item[1], 'Help text...', item[2])
			menu[i][0] = self.menu.Append(*item)

		# [menu.MenuItems[i].Enable(False) for i, x in enumerate(self.menu) if x[1:] and x[1] is False]

		# add callbacks to menu items -- seems the callback function has to be bound?
		# create a lambda (the inner one) which calls the intended callback, and bind it to self
		bound_func = lambda func, args: partial(lambda s2, e: getattr(self, func)(e, *args), self)

		# params for Bind for each menuitem with callbacks (item[2] with args in item[3:])
		bind_params = [(wx.EVT_MENU, bound_func(item[3], item[4:]), item[0]) for item in menu if item[3:]]
		list(itertools.starmap(self.tb.Bind, bind_params))

	def OnClose(self, event):
		print 'program closed', event
		self.running = False
		self.tb.RemoveIcon()
		self.tb.Destroy()
		self.frame.Destroy()
		self.Exit()

	def FrameFocus(self, event):
		print 'FrameFocus:', event, event.EventObject, event.Id

	def TaskBarFocus(self, event):
		print 'TaskBarFocus:', event, event.EventObject, event.Id

	def TaskBarMenu(self, event):
		print 'TaskBarMenu:', event, event.EventObject, event.Id
		self.tb.PopupMenu(self.menu)

	def toggle_host(self, event, option=0, host=None):
		if host:
			option = next((i for i, x in enumerate(self.hosts) if x['url'] == host), None)
			if option is None: return
		else:
			host = self.hosts[option]['url']
		flag = self.hosts[option]['check'] = not self.hosts[option]['check']
		id = event.Id if event else self.option_ids['toggle_host'][option]
		self.menu.FindItemById(id).Check(flag)
		# print 'toggle_host: id=%d, option=%d, host=%s' % (id, option, host)

	def set_scale(self, event, option=0, scale=None):
		self.scale = scale or self.scale_options[option]
		id = event.Id if event else self.option_ids['set_scale'][option]
		self.menu.FindItemById(id).Check()
		# print 'set_scale: id=%d, option=%d, scale=%d' % (id, option, self.scale)

	def set_rate(self, event, option=0, rate=None):
		self.rate = rate or self.rate_options[option]
		id = event.Id if event else self.option_ids['set_rate'][option]
		self.menu.FindItemById(id).Check()
		# print 'set_rate: id=%d, option=%d, rate=%d' % (id, option, self.rate)

	def set_slice(self, event, option=0, slice=None):
		self.slice = slice or self.slice_options[option]
		id = event.Id if event else self.option_ids['set_slice'][option]
		self.menu.FindItemById(id).Check()
		# print 'set_slice: id=%d, option=%d, slice=%d' % (id, option, self.slice)


if __name__ == '__main__':
	from config import config
	app = App(None, **config.wxapp)
	app.update({'google.com': [(x, x) for x in xrange(200, 20, -10)]})
	app.MainLoop()
