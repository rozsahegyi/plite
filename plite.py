import os, threading, socket, time, itertools, logging
from collections import deque
import ping, config, wxtray

logging.basicConfig(format='%(asctime)-15s %(name)-10s  %(message)s', filename=config.config.logfile or None)
logger = logging.getLogger('plite')
logger.setLevel(logging.INFO)


class Plite(object):
	def __init__(self, config):
		self.running = False
		self.config = config
		self.config.hosts = dict.fromkeys(self.config.hosts, None)
		self.wxapp = wxtray.App(self)
		self.charts = Charts(self)
		logger.info('Setting up hosts...')
		self.pingers = [Pinger(url, **config.pinger) for url in sorted(self.config.hosts)]
		self.saved = 0

	@property
	def results(self):
		# only used every x seconds once, no need to cache
		self.last_results = [pinger.results[-1][1] for pinger in self.pingers]
		logger.info(self.last_results)
		return [(pinger.destination, pinger.results) for pinger in self.pingers if self.config.hosts[pinger.destination]]

	def ping_hosts(self):
		"""Runs threads for pinging each host, blocks for timeout seconds."""
		for x in self.pingers: threading.Thread(target=x.ping).start()
		time.sleep(self.config.pinger.timeout + 0.3)
		for x in self.pingers:
			if len(x.results[-1]) > 2: msg = ', '.join(map(str, x.results[-1][2:]))
			elif not x.results[-1][1]: continue # 'response timed out'
			elif x.results[-1][1] < 0: msg = 'sending timed out'
			else: continue
			logger.info('%-20s  %s', x.destination, msg)

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
		logger.info('Plite running...')

		while self.running and self.wxapp.running:
			now = time.time()
			if time_to_ping(now):
				last += self.config.wxapp.rate
				self.ping_hosts()
				self.update_wxapp()
			if time_to_save(now):
				self.saved = now + self.config.save_interval
				threading.Thread(target=self.save).start()
			time.sleep(0.05)
		logger.info('Plite stopped.')

	def save(self):
		for x in self.pingers: self.save_results(x)

	def save_results(self, pinger):
		data = pinger.unsaved_results()
		if not data: return
		logger.info('saving: %s %s', pinger.destination, data)
		data = '\n'.join(':'.join(map(str, x)) for x in data) + '\n'
		stamp = time.strftime('%Y%m%d', time.localtime(pinger.today))
		save_dir = self.config.logs
		if not os.path.exists(save_dir): os.makedirs(save_dir)
		filename = '%s_%s.txt' % (pinger.destination, stamp)
		filename = os.path.join(save_dir, filename)
		with open(filename, 'a') as f: f.write(data)


class Pinger(object):
	blank = (0, -1)
	results = []

	def __init__(self, url='', timeout=0.8, stored=100, **kw):
		if not url: raise Exception('Pinger instances always need an url.')
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
	def __init__(self, app):
		self.app = app
		self.default_interval = (-30, 0)

	def __getattr__(self, key):
		"""Get some attributes from the main config or the wxapp subdict."""
		# used for: icon_size, scale, rate
		return getattr(self.app.config, key, None) or getattr(self.app.config.wxapp, key, None)

	def compose_icon(self, results, width=None, interval=None, host=None):
		"""Generates a bytearray needed for an icon.

		Currently just takes the last x results, ignoring the slice setting.
		"""
		if not results: return None
		if not width: width = self.icon_size
		if not interval: interval = self.default_interval
		if host:
			results = filter(lambda x: x[0] == host, results) if isinstance(host, str) else [results[host]]

		results = self.slice_times(results, width)
		charts = len(results)
		size = int(width / charts)
		extra_rows = width - size * charts
		data = [self.icon_section(x, size, not i and extra_rows) for i, x in enumerate(results)]
		data = list(itertools.chain(*data))
		data = self.icon_blips(data)
		return bytearray(x for pixel in data for x in pixel)

	def slice_times(self, results, num=None, interval=None):
		"""Takes the times of the last num elements in each result.

		TODO: consider the timestamps of results and the current timeframe (slice setting)

		results: ((url, ((time1, ping), (time2, ping2), ...)), (url, ...))
		returns: [[time1, time2, ...], [time3, time4, ...]]
		"""
		if len(results) > 4: results = results[0:4]
		slice_result = lambda result: [result[1][i][1] for i in xrange(-num, 0)]
		return map(slice_result, results)

	def icon_blips(self, data, interval=4):
		"""Sets some blips along the icon bottom to indicate movement."""
		size = self.icon_size
		last_index = size**2
		blips = size / interval
		# offset decreases as time passes, use an interval-sized part
		offset = (size - int(time.time() / self.rate % size) - 1) % interval
		# add this to the last index, and reduce it for each blip
		indexes = [last_index + offset - int(interval * x) for x in xrange(1, 1 + blips)]
		# invert colors of pixels at these indexes
		for x in indexes: data[x] = [255 - b for b in data[x]]
		return data

	def icon_section(self, data, size=None, extra_rows=0):
		if not size: size = self.icon_size
		scale = float(self.scale)

		# note on helper methods:
		# normalize: ping_time into a 0..1 number based on self.scale
		# black/colored: tuple of (r, g, b) tuples, black or green-yellow-red (normalized range)
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
