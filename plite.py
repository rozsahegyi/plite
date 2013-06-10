# coding=utf-8

import sys, os, re, json, time
sys.path.append(os.path.realpath(os.path.curdir + '\\Lib\\site-packages'))

import socket
from flask import Flask, render_template, make_response
from ping import Ping
from systray import SysTrayIcon

from PIL import Image
from StringIO import StringIO
import wx, threading, collections, itertools


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
		super(App, self).__init__(False)

	def OnInit(self):
		self.frame = wx.Frame(None, wx.ID_ANY, 'Plite 1.0')#, style=wx.FRAME_NO_TASKBAR)
		self.tb = wx.TaskBarIcon()
		self.Bind(wx.EVT_SET_FOCUS, self.OnKeyPress)
		self.frame.Bind(wx.EVT_SET_FOCUS, self.OnKeyPress)
		self.tb.Bind(wx.EVT_SET_FOCUS, self.OnKeyPress)
		self.tb.frame = self.frame
		self.running = False

		wx.EVT_CLOSE(self.frame, self.OnClose)
		wx.EVT_TASKBAR_LEFT_UP(self.tb, self.TaskBarClick)
		wx.EVT_TASKBAR_RIGHT_UP(self.tb, self.TaskBarClick)

		self.menu = wx.Menu()
		item1 = self.menu.Append(wx.NewId(), 'Item 1\tENTER')
		item2 = self.menu.Append(wx.NewId(), 'Item 2\tENTER')
		item3 = self.menu.Append(wx.NewId(), 'Quit')

		self.tb.Bind(wx.EVT_MENU, self.OnKeyPress, item1)
		self.tb.Bind(wx.EVT_MENU, self.OnKeyPress, item2)
		self.tb.Bind(wx.EVT_MENU, self.OnClose, item3)

		self.pings = collections.deque(((0, 50),) * self.store_pings)
		self.start_updates()
		return True

	def OnClose(self, event):
		print 'program closed', event
		self.tb.RemoveIcon()
		self.tb.Destroy()
		self.frame.Destroy()

	def OnKeyPress(self, event):
		print 'keypress:', event, event.EventObject, event.Id

	def TaskBarClick(self, event):
		self.tb.PopupMenu(self.menu)

	def ItemOnclick(self, event):
		print 'item onclick', event, dir(event)

	def start_updates(self):
		thread = threading.Thread(target=self.run_updates)
		thread.start()

	def ping_result(self, timestamp, res):
		last = self.pings[-1] if self.pings else (0, 0)
		if last[0] > timestamp: return
		self.pings.append((timestamp, res))
		if len(self.pings) > self.store_pings: self.pings.popleft()

	def run_updates(self):
		self.running = True
		last = int(time.time())
		while self.running:
			now = time.time()
			if now >= last:
				last += self.ping_interval
				self.ping_result(now, self.pinger.ping())
				self.update_icon()
			else:
				time.sleep(0.05)

	def update_icon(self, data=None):
		if not data: data = self.icon_map()
		icon = wx.EmptyIcon()
		icon.CopyFromBitmap(wx.BitmapFromBuffer(self.icon_size, self.icon_size, data))
		self.tb.SetIcon(icon) # RemoveIcon

	def icon_map(self):
		# print self.icon_size, self.slowest_ping
		normalize = lambda x: (min((x[1] or 1000) / float(self.slowest_ping), 1))
		colorize = lambda x: (int(255 * min(1, 2 * x)), int(255 * min(1, 2 * (1 - x))), 0)
		# to_column = lambda x: (0, 0, 0) * int(self.icon_size * (1 - round(x))) + colorize(x) * int(round(x))
		to_column = lambda x: ((0, 0, 0),) * int(round(self.icon_size * (1 - x))) + (colorize(x),) * int(round(self.icon_size * x))
		# print 'pings:', self.pings
		# print 'pings:', list(self.pings)[-self.icon_size:]
		data = map(normalize, list(self.pings)[-self.icon_size:])
		# print 'normalized:', data
		data = map(to_column, data)
		# print 'columns:', data
		data = zip(*data)
		# print 'flatten:', data
		data = list(itertools.chain(*data))
		# print 'flatten:', list(itertools.chain(*data))
		return bytearray(list(itertools.chain(*data)))
		# return '\xff\xff\xff\xff\x00\x00' * (8 * 16)

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
		'interval': 5,
		'store_pings': 640,
		'slowest_ping': 300,
		'ping_timeout': 0.8,
		'ping_interval': 1,
		'icon_size': 16,
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
