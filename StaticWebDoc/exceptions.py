import jinja2
import pathlib

def get_jinja_message(ex):
	match ex:
		case jinja2.TemplateNotFound() | jinja2.TemplatesNotFound():
			return f"[{type(ex).__name__}] {', '.join(ex.templates)}"
		case jinja2.TemplateSyntaxError():
			return f"[{type(ex).__name__}]\n- Location {ex.filename}:\n- -  ({ex})"
		case default:
			return f"[{type(ex).__name__}] {ex}"

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
			if isinstance(self.__parent, jinja2.TemplateError):
				return f"While rendering {self.__template} encountered error: {get_jinja_message(self.__parent)}"
			else:
				return f"While rendering {self.__template} encountered error: [{type(self.__parent).__name__}] {self.__parent.message}"

	def __str__(self):
		return f"RenderErrors(message={self.message})"