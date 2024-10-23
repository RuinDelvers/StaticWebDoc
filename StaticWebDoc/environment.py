import jinja2

class CustomEnvironment(jinja2.Environment):
	""" Custom environment for this type of project. """

	""" This is a map that maps template names to a map of keys to data. """
	__cached_map = {}
	__data_map = {}

	__current_env = None

	def add_cache(self, template, key, data):
		if template not in self.__cached_map:
			self.__cached_map[template] = {}

		self.__cached_map[template][key] = data

	def has_cache(self, template, key):
		if template in self.__cached_map:
			return key in self.__cached_map[template]
		else:
			return False

	def get_cache(self):
		return self.__cached_map

	def clear_cache(self):
		self.__cached_map = {}


	def add_data(self, template, key, data):
		if template not in self.__data_map:
			self.__data_map[template] = {}

		self.__data_map[template][key] = data

	def has_data(self, template, key):
		if template in self.__data_map:
			return key in self.__data_map[template]
		else:
			return False

	def get_data(self):
		return self.__data_map

	def clear_data(self):
		self.__data_map = {}

	@property
	def data_env(self):
		if self.__current_env is None:
			raise ValueError("Attempted to set data in a null environment.")
		
		return self.__current_env
	
	def set_data_env(self, name):
		self.__current_env = name

	def clear_env(self):
		self.__current_env = None