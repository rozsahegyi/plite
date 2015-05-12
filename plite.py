import os, threading, socket, time, itertools
from collections import deque
import ping, config, wxtray

def message(msg, *args):
	print '%s.%03d  %s' % (time.strftime('%H:%M:%S'), time.time() % 1 * 1000, msg), args or ''
	pass

class Plite(object):
	def __init__(self, config):
		self.running = False
		self.config = config
		self.wxapp = wxtray.App(self, hosts=config.hosts, icon_size=config.icon_size, **config.wxapp)
		self.charts = Charts(self, icon_size=config.icon_size)
		message('Setting up hosts...')
		self.hosts = [Pinger(url, **config.pinger) for url in config.hosts]
		self.saved = 0

	@property
	def results(self):
		# only used every x seconds once, no need to cache
		return [(pinger.destination, pinger.results) for pinger in self.hosts]

	def ping_hosts(self):
		"""Runs threads for pinging each host, blocks for timeout seconds."""
		for x in self.hosts: threading.Thread(target=x.ping).start()
		time.sleep(self.config.pinger.timeout + 0.3)
		for x in self.hosts:
			if len(x.results[-1]) > 2: msg = ', '.join(map(str, x.results[-1][2:]))
			elif not x.results[-1][1]: msg = 'response timed out'
			elif x.results[-1][1] < 0: msg = 'sending timed out'
			else: continue
			message('%-20s  %s' % (x.destination, msg), x.results[-1])

	def update_wxapp(self):
		self.wxapp.update_event(self.charts.compose_icon(self.results))

	def start(self):
		threading.Thread(target=self.run).start()
		self.update_wxapp()
		self.wxapp.MainLoop()

	def run(self):
		last = int(time.time())
		time_to_ping = lambda now: now >= last
		time_to_save = lambda now: now >= self.saved
		self.running = True
		message('Plite running...')

		while self.running and self.wxapp.running:
			now = time.time()
			if time_to_ping(now):
				last += self.wxapp.rate
				# message('Pinging...')
				self.ping_hosts()
				# message('Updating...')
				self.update_wxapp()
			if time_to_save(now):
				self.saved = now + self.config.save_interval
				threading.Thread(target=self.save).start()
			time.sleep(0.05)
		message('Plite stopped.')

	def save(self):
		for x in self.hosts: self.save_results(x)

	def save_results(self, pinger):
		data = pinger.unsaved_results()
		if not data: return
		print 'saving:', pinger.destination, data
		data = '\n'.join(':'.join(map(str, x)) for x in data) + '\n'
		stamp = time.strftime('%Y%m%d', time.localtime(pinger.today))
		save_dir = self.config.save_dir
		if not os.path.exists(save_dir): os.makedirs(save_dir)
		filename = '%s_%s.txt' % (pinger.destination, stamp)
		filename = os.path.join(save_dir, filename)
		# with open(filename, 'a') as f: f.write(data)


# class Pinger(ping.Ping):
class Pinger(object):
	blank = (0, -1)
	results = []

	def __init__(self, url='', timeout=0.8, stored=100, **kw):
		if not url: raise Exception('Pinger instances always need an url.')
		# super(Pinger, self).__init__(url, timeout * 1000)
		self.destination = url
		self.timeout = timeout * 1000
		self.results = deque((self.blank,) * stored, maxlen=stored)
		self.stored = stored
		self.counter = 0
		self.lock = threading.Semaphore()
		self.update_times()

	def update_times(self):
		# smaller numbers take less on the disk, and easier to work with,
		# so store timestamps relative to the start of the day
		t = time.localtime()
		today = list(t[0:3] + (0, 0, 0) + t[6:])
		tomorrow = today[0:2] + [today[2] + 1] + today[3:]
		self.today = int(time.mktime(today))
		self.tomorrow = int(time.mktime(tomorrow))
		self.saved_at = 0

	@property
	def timestamp(self):
		now = int(time.time())
		if now >= self.tomorrow: self.update_times()
		return now - self.today

	def ping(self):
		pinger = ping.Ping(self.destination, self.timeout)
		timestamp = self.timestamp
		counter = self.add_result(timestamp)
		res, error = 0, ()

		# res becomes a positive number or None (failed ping, no exception),
		# otherwise a socket exception is raised
		try: res = pinger.do()
		except socket.error as e: error = (e.__class__.__name__, e.message) + e.args
		res = int(max(1, res)) if res else 0

		# find the slot which this result should go into
		index = self.counter - counter
		if index > self.stored: return
		self.results[-index] = (timestamp, res) + error

	def add_result(self, timestamp):
		# add a slot for this result, and store the counter to index it later
		self.results.append((timestamp, -1))
		self.counter = (self.counter + 1) % self.stored
		return self.counter - 1

	def result_slice(self, interval=None):
		# no slicing for deque, have to take results one by one instead
		# this means results can change during iteration, so do it backwards,
		# this way the only problem are duplicated points, which are ignored
		# this is O(n) because of the temporary deque, slightly better than
		# appending to a list + reversing

		now = self.timestamp
		if not interval: interval = now - 60
		if isinstance(interval, int): interval = [interval, 0]
		if not interval[1]: interval[1] = now
		prev = None
		deck = deque()

		for index in xrange(1, self.stored + 1):
			point = self.results[-index]
			# timestamp larger than upper bounds, or duplicated point
			if point[0] > interval[1] or prev == point: continue
			# timestamp smaller than lower bounds, or previous day's data
			if point[0] <= interval[0] or (prev and point[0] > prev[0]): break
			prev = point
			deck.appendleft(point)
		return deck

	def unsaved_results(self, interval=None):
		results = self.result_slice((self.saved_at, self.tomorrow))
		if len(results): self.saved_at = results[-1][0]
		return results


class Charts(object):
	def __init__(self, app, icon_size):
		self.app = app
		self.icon_size = icon_size

	def __getattr__(self, key):
		return getattr(self.app, key)

	def compose_icon(self, results, width=None, interval=None, host=None):
		if not results: return None
		if host:
			results = filter(lambda x: x[0] == host, results) if isinstance(host, str) else [results[host]]
		if not width: width = self.icon_size
		if not interval: interval = (-30, 0)
		# print [results[2][1][x] for x in xrange(-10, 0)]
		results = self.slice_results(results)
		charts = len(results)
		size = int(width / charts)
		extra_rows = width - size * charts
		data = [self.icon_section(x, size, not i and extra_rows) for i, x in enumerate(results)]
		data = list(itertools.chain(*data))
		data = self.icon_blips(data)
		return bytearray(x for pixel in data for x in pixel)

	def slice_results(self, results, width=None, interval=None):
		# results: ((url, ((timestamp, ping_time), (time, ping))), (url, ...))
		# deque can't be sliced, and itertools.islice doesn't support negative indexes
		num = 16
		single_time = lambda res, i: res[1][i][1]
		slice_result = lambda result: [single_time(result, i) for i in xrange(-num, 0)]
		if len(results) > 4: results = results[0:4]
		return map(slice_result, results)

	def icon_blips(self, data):
		"""Sets some blips along the icon bottom to indicate movement."""
		size = self.icon_size
		offset = size**2
		offset += (size - int(time.time() / self.app.wxapp.rate % size) - 1) % 4
		indexes = [-0.25 * x for x in xrange(1, 5)]
		indexes = (offset + int(x * size) for x in indexes)
		for x in indexes: data[x] = [255 - b for b in data[x]]
		return data

	def icon_section(self, data, size=None, extra_rows=0):
		if not size: size = self.icon_size
		scale = float(self.app.wxapp.scale)

		# note on helper methods:
		# normalize: ping_time into a 0..1 number based on self.scale
		# black/colored: (r, g, b) tuple, black or green-yellow-red (based on a normalized value)
		# pixels: 0..x row black + 0..x row colored + 1 row black
		# column: get pixels for a value and height
		normalize = lambda value: 0 if value < 0 else (min(1, (value or 1000) / scale))
		black = lambda h: ((0, 0, 0),) * h
		colored = lambda n, h: ((int(255 * min(1, 2 * n)), int(255 * min(1, 2 * (1 - n))), 0),) * h
		pixels = lambda n, h: black(size - 1 - h + int(extra_rows)) + colored(n, h) + black(1)
		column = lambda normval: pixels(normval, max(1, int(round((size - 1) * normval))) if normval else 0)

		data = map(column, map(normalize, data))
		data = zip(*data) # flips the generated pixels (x,y -> y,x)
		return list(itertools.chain(*data)) # flattened list of pixel tuples


if __name__ == '__main__':
	plite = Plite(config.config)
	plite.start()
