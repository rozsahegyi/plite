import json

config = {
	'save_interval': 10, # save results every x seconds
	'save_dir': 'logs/plite/',
	'hosts': ['192.168.3.1', 'google.com', 'imgur.com'],
	'icon_size': 16,
	'pinger': {
		'timeout': 0.7, # should be somewhat less than the smallest ping rate
		'stored': 3600, # store this many results in memory
	},
	'wxapp': {
		'menu': [
			['Hosts:'],
			['hosts'],
			'',
			['Chart scale:'],
			['scale_options', 100, 250, 500, 750, 1000],
			'',
			['Refresh rate:'],
			['rate_options', 1, 2, 5, 10],
			'',
			['Show the last:'],
			['slice_options', 15, 30, 60, 120, 300, 600, 1800],
			'',
			['Quit (Double-click)', None, 'OnClose'],
		],
	},
	'webapp': {
	},
}


class mapping(dict):
	"""Dict with attribute access, credits: http://stackoverflow.com/a/14620633/1393194"""
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

config = mapping(config)
