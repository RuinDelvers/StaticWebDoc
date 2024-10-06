import jinja2

class CustomEnvironment(jinja2.Environment):
	""" Custom environment for this type of project. """

	""" This is a map that maps template names to a map of keys to data. """
	__cached_map = {}

	def add_data(self, template, key, data):
		if template not in self.__cached_map:
			self.__cached_map[template] = {}

		self.__cached_map[template][key] = data

	def get_cache(self):
		return self.__cached_map

	def clear_cache(self):
		self.__cached_map = {}