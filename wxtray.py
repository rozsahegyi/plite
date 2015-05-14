import sys, os, itertools, logging
from collections import defaultdict
from functools import partial
sys.path.append(os.path.realpath(os.path.curdir + '\\Lib\\site-packages'))
import wx, wx.lib.newevent

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


class App(wx.App):
	def __init__(self, app):
		self.app = app
		self.running = False
		self.UpdateEvent, self.EVT_UPDATE = wx.lib.newevent.NewEvent()
		super(App, self).__init__(False)

	@property
	def config(self):
		return self.app.config.wxapp

	@property
	def hosts(self):
		return self.app.config.hosts

	@property
	def host_order(self):
		# no caching, used only at initial menu generation and click events
		return sorted(self.app.config.hosts)

	def OnInit(self):
		self.frame = wx.Frame(None, wx.ID_ANY, 'Plite 1.0')
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
		self.set_option(None, option=1, key='scale')
		self.set_option(None, option=0, key='rate')
		self.set_option(None, option=2, key='slice')
		self.running = True
		return True

	def update_event(self, data):
		wx.PostEvent(self.tb, self.UpdateEvent(data=data))

	def update(self, event):
		if not event.data: return
		icon = wx.EmptyIcon()
		size = self.app.config.icon_size
		icon.CopyFromBitmap(wx.BitmapFromBuffer(size, size, event.data))
		# add the latest ping info to the tooltip
		if self.tb:
			self.tb.SetIcon(icon, ' | '.join('%d ms' % x for x in self.app.last_results))

	def setup_menu(self):
		# methods to generate various menu items
		time_format = lambda sec: '%d seconds' % sec if sec < 60 else '%.2g minutes' % (sec / 60)
		methods = {
			'separator': lambda a: [[None]],
			'normal': lambda a: [[a[0], len(a) > 1 and a[1] or wx.ITEM_NORMAL] + a[2:]],
			'scale_options': lambda a: [['%g ms' % x, wx.ITEM_RADIO, 'set_option', i, 'scale', x] for i, x in enumerate(a[1:])],
			'rate_options': lambda a: [['%g sec' % x, wx.ITEM_RADIO, 'set_option', i, 'rate', x] for i, x in enumerate(a[1:])],
			'slice_options': lambda a: [[time_format(x), wx.ITEM_RADIO, 'set_option', i, 'slice', x] for i, x in enumerate(a[1:])],
			'hosts': lambda a: [[x, wx.ITEM_CHECK, 'toggle_host', i] for i, x in enumerate(self.host_order)],
		}

		def transform(item):
			# apply the proper method for menu items, and store original options
			if item and item[1:] and item[0].endswith('_options'):
				self.options[item[0][0:-8]] = item[1:]
			method = 'separator' if not item or not item[0] else 'normal' if item[0] not in methods else item[0]
			return methods[method](item)

		self.options = defaultdict(list)
		self.option_ids = defaultdict(dict)
		self.menu = wx.Menu()

		# generate menu items, flatten the nested list
		menu = [item for sub in map(transform, self.config.menu) for item in sub]

		# here menu is a list of: ['name', item_kind, callback, callback_args]
		for i, item in enumerate(menu):
			menu[i] = item = [wx.NewId()] + item if item[0] else [wx.ID_SEPARATOR]
			# store the ids of multi-option elements associated with callbacks,
			# so it's simpler to find the menu item for a given option
			if len(item) > 4:
				func, option = item[3:5]
				if len(item) > 5: func = item[5]
				self.option_ids[func][option] = item[0]
			if len(item) > 1: item = (item[0], item[1], 'Help text...', item[2])
			menu[i][0] = self.menu.Append(*item)

		# check each host option
		for i, x in enumerate(self.host_order): self.toggle_host(None, i)

		# add callbacks to menu items -- seems the callback function has to be bound?
		# create a lambda (the inner one) which calls the intended callback, and bind it to self
		bound_func = lambda func, args: partial(lambda s2, event: getattr(self, func)(event, *args), self)

		# params for Bind for menuitem callbacks (method is item[2], args are item[3:])
		bind_params = [(wx.EVT_MENU, bound_func(item[3], item[4:]), item[0]) for item in menu if item[3:]]
		list(itertools.starmap(self.tb.Bind, bind_params))

	def toggle_host(self, event, option=0, host=None):
		if host:
			if host not in self.hosts: return
			option = self.host_order.index(host)
		else:
			host = self.host_order[option]
		self.hosts[host] = not self.hosts[host]
		id = event.Id if event else self.option_ids['toggle_host'][option]
		logger.debug('toggle_host: id=%d, option=%d, host=%s, status=%s', id, option, host, self.hosts[host])
		self.menu.FindItemById(id).Check(self.hosts[host])

	def set_option(self, event, option=0, key=None, value=None):
		"""Handles setting multi-choice options (radio buttons)."""
		self.config[key] = value or self.options[key][option]
		# if no event, get the stored menuitem id
		id = event.Id if event else self.option_ids[key][option]
		self.menu.FindItemById(id).Check()
		logger.debug('set_option: id=%d, option=%d, %s=%d', id, option, key, self.config[key])

	def OnClose(self, event):
		logger.debug('OnClose: %s', event)
		self.running = False
		self.tb.RemoveIcon()
		self.tb.Destroy()
		self.frame.Destroy()
		self.Exit()

	def FrameFocus(self, event):
		logger.debug('FrameFocus: %s %s %s', event, event.EventObject, event.Id)

	def TaskBarFocus(self, event):
		logger.debug('TaskBarFocus: %s %s %s', event, event.EventObject, event.Id)

	def TaskBarMenu(self, event):
		logger.debug('TaskBarMenu: %s %s %s', event, event.EventObject, event.Id)
		self.tb.PopupMenu(self.menu)

