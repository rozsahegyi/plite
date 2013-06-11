# coding=utf-8

import sys, os, re, json, time, socket
import threading, collections, itertools
from functools import partial
from ping import Ping
sys.path.append(os.path.realpath(os.path.curdir + '\\Lib\\site-packages'))

import wx
from flask import Flask, render_template, make_response
# from PIL import Image
# from StringIO import StringIO


class mapping(dict):
	"""Dict with attribute access, credits to: http://stackoverflow.com/a/14620633/1393194"""
	def __init__(self, content, *args, **kw):
		if isinstance(content, (str, unicode)):
			content = self.unpack(content)
		elif not hasattr(content, 'iteritems'):
			raise Exception('mapping with %s argument' % type(content))
		super(mapping, self).__init__(content, *args, **kw)
		self.__dict__ = self
		[self.__setitem__(k, mapping(v)) for k, v in self.iteritems() if isinstance(v, dict)]

	def pack(self): return json.dumps(self, ensure_ascii=False)
	def unpack(self, content): return json.loads(content)

def index():
	content = "running pings..."
	return render_template('netwatch.html', content=content)

class App(wx.App):
	def __init__(self, config):
		[setattr(self, k, v) for k, v in config.iteritems()]
		self.running = False
		self.pings = collections.deque(((0, 1),) * self.store_pings)
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
		self.tb.Bind(wx.EVT_TASKBAR_RIGHT_UP, self.TaskBarMenu)

		self.setup_menu()
		# self.tb.SetIcon(wx.Icon('icons/favicon.ico', wx.BITMAP_TYPE_ICO))
		self.update_icon()
		self.set_interval(self.interval)
		self.start_updates()
		return True

	def setup_menu(self):
		menu = wx.Menu()
		menu_item = lambda item: (wx.NewId(), item[0]) if item[0] else (wx.ID_SEPARATOR, '')
		[item.__setitem__(0, menu.Append(*menu_item(item))) for item in self.menu]

		# seems the callback function has to be bound (there has to be a simpler way though)
		# create a lambda (calling the intended callback with passed arguments), and bind it to self
		bound_func = lambda s1, f: partial(lambda s2, e: getattr(s1, f[1])(e, *f[2:]), s1)
		events = [(wx.EVT_MENU, bound_func(self, item), item[0]) for item in self.menu if item[1:]]
		list(itertools.starmap(self.tb.Bind, events))

		self.menu = menu

	def OnClose(self, event):
		print 'program closed', event
		self.running = False
		self.tb.RemoveIcon()
		self.tb.Destroy()
		self.frame.Destroy()
		self.Exit()

	def FrameFocus(self, event):
		# print 'FrameFocus:', event, event.EventObject, event.Id
		pass

	def TaskBarFocus(self, event):
		# print 'TaskBarFocus:', event, event.EventObject, event.Id
		pass

	def TaskBarMenu(self, event):
		# print 'TaskBarMenu:', event, event.EventObject, event.Id
		# print self.menu.MenuItems[0].Text
		self.tb.PopupMenu(self.menu)

	def MenuClick(self, event, *args):
		# print 'OnKeyPress:', event, event.EventObject, event.Id
		pass

	def set_interval(self, event, interval=1):
		self.interval = interval
		self.menu.MenuItems[0].Text = '%s: %g sec' % (self.menu.MenuItems[0].Text.split(':')[0], interval)
		print 'set_interval:', interval

	def start_updates(self):
		thread = threading.Thread(target=self.run_updates)
		thread.start()

	def run_updates(self):
		self.running = True
		last = int(time.time())
		while self.running:
			now = time.time()
			if now >= last:
				last += self.interval
				self.ping_result(now, self.pinger.ping())
				self.update_icon()
			else:
				time.sleep(0.05)

	def ping_result(self, timestamp, res):
		last = self.pings[-1] if self.pings else (0, 0)
		if last[0] > timestamp: return
		self.pings.append((timestamp, res))
		if len(self.pings) > self.store_pings: self.pings.popleft()

	def update_icon(self, data=None):
		if not data: data = self.icon_map()
		icon = wx.EmptyIcon()
		icon.CopyFromBitmap(wx.BitmapFromBuffer(self.icon_size, self.icon_size, data))
		if self.tb: self.tb.SetIcon(icon) # make sure the taskbar still exists # RemoveIcon

	def icon_map(self):
		# helpers:
		# normalize ping time in the 0..1 range (ratio to self.slowest_ping)
		# colors for a 0..1 range
		# pixel columns: self.icon_size * (1-x) * black_pixels + self.icon_size * x * color_pixels
		normalize = lambda x: (min((x[1] or 1000) / float(self.slowest_ping), 1))
		colorize = lambda x: (int(255 * min(1, 2 * x)), int(255 * min(1, 2 * (1 - x))), 0)
		to_column = lambda x: ((0, 0, 0),) * int(round(self.icon_size * (1 - x))) + (colorize(x),) * int(round(self.icon_size * x))

		data = map(normalize, list(self.pings)[-self.icon_size:])
		data = map(to_column, data)
		data = zip(*data) # flips the generated pixels (along the nw-se axis)
		data = list(itertools.chain(*data)) # flattened list of pixel tuples

		# set two blips alongside the top of the image
		i = (self.icon_size - int(time.time() / self.interval % 16) - 1) % 8
		blip = (255, 255, 255)
		indexes = [0, self.icon_size, 0.5 * self.icon_size, 1.5 * self.icon_size]
		[data.__setitem__(i + int(x), blip) for x in indexes]

		return bytearray(list(itertools.chain(*data)))

class Pinger(Ping):
	def __init__(self, url, timeout=None):
		Ping.__init__(self, url, timeout * 1000)

	def ping(self, url=None, timeout=None):
		if url: self.destination, self.dest_ip = url, socket.gethostbyname(url)
		if timeout: self.timeout = timeout
		try: res = self.do()
		except socket.error, e: res = e
		return res
		# result = make_response(str(res), 200)
		# result.headers['Content-type'] = 'json'#text/json'
		# return result


if __name__ == '__main__':

	config = mapping({
		'pinger': ['www.google.com', 0.8],
		'store_pings': 640,
		'slowest_ping': 300,
		'interval': 1,
		'icon_size': 16,
		'menu': [
			['Refresh rate:'],
			['0.5 sec', 'set_interval', 0.5],
			['1 sec', 'set_interval', 1],
			['2 sec', 'set_interval', 2],
			['5 sec', 'set_interval', 5],
			['10 sec', 'set_interval', 10],
			[''],
			['Quit (Double-click)', 'OnClose'],
		],
	})

	config.pinger = Pinger(*config.pinger)
	app = App(config)
	app.MainLoop()
	exit()

	# icon = Image.open('icons/boilerplate.png')
	# icon.save(f, 'BMP')
	# f = f.getvalue()[14:]
	# l = len(f)
	# header = (0, 0, 1, 0, 1, 0) + (16, 16, 0, 0, 1, 0, 32, 0) + (l % 16, (l % 256) / 16, (l / 256) % 16, (l / 256) / 16) + (22, 0)
	# print header
	# header = bytearray(header)
	# with open('icons/asd.png', 'wb') as ff: ff.write(f)
	# with open('icons/asd2.ico', 'wb') as ff: ff.write(header + f)
	# exit()

	# icon = Image.fromstring('RGB', (16, 16), '\xff\xff\xff\xff\x00\x00' * (8 * 16))
	# icon.save(f, 'GIF')
	# icon.save('sample.gif', 'GIF')
	# with open('sample2.gif', 'wb') as ff: ff.write(f.getvalue())


	# app = Flask(__name__)
	# config = mapping({'ping': { 'url': 'www.google.com', 'timeout': 2, 'interval': 5 }})
	# pinger = Pinger(config.ping.url, timeout=config.ping.timeout)

	# app.add_url_rule('/ping', 'ping', pinger.ping)
	# app.add_url_rule('/', 'index', index)
	# app.run(debug=True)
