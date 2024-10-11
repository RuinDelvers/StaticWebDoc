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

	@property
	def message(self):
		if issubclass(type(self.__parent), RenderError):
			return f"While rendering {self.__template}:\n- {self.__parent}"
		else:
			if hasattr(self.__parent, "message"):
				return f"While rendering {self.__template} encountered error: [{type(self.__parent).__name__}] {self.__parent.message}"
			else:
				return f"While rendering {self.__template} encountered error: [{type(self.__parent).__name__}] {self.__parent.message}"

	def __str__(self):
		return f"RenderErrors(message={self.message})"