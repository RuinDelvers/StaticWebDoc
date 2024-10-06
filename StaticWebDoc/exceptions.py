class RenderError(Exception):
	""" Exception raised during rendering to keep track of template render errors. """

	def __init__(self, template, parent=None):
		self.__template = template
		self.__parent = parent

	@property
	def parent(self):
		return self.__parent

	@property
	def template(self):
		return self.__template	

	def __str__(self):
		if issubclass(self.__parent, RenderError):
			return f"While rendering {self.__template}:\n- {self.__parent}"
		else:
			return f"While rendering {self.__template} encountered error: {self.__parent}"