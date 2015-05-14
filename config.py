
config = {
	'logfile': '',#'plite.log',
	'logs': 'logs/',
	'save_interval': 10, # save results every x seconds
	'hosts': ['yahoo.com', 'google.com', 'imgur.com'],
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
	"""Dict with attribute access. Accepts dict-like objects or tuple list."""
	def __init__(self, content=None, *args, **kw):
		content = content.iteritems() if hasattr(content, 'iteritems') else content or []
		if content:
			content = ((k, mapping(v) if isinstance(v, dict) else v) for k, v in content if k and k[0] != '_')
		super(mapping, self).__init__(content, *args, **kw)
		self.__dict__ = self
	def __getattr__(self, key):
		return None


config = mapping(config)
