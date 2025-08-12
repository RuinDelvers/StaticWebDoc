import sys
import pathlib
import jinja2
import importlib
import inspect

def map_dirs(root, dirs):
	return list(map(
		lambda temp: str(root/temp),
		dirs
	))

class ModuleLoader:
	def __init__(self):
		self.__modules = {}

	def load_module(self, path):
		if path.startswith("@"):
			index = path.index("/")
			mname = path[1: index]
			nested_template = path[index + 1:]

			if mname in self.__modules:
				return self.__modules[mname], mname, nested_template



			module = importlib.import_module(mname)

			if "__init__.py" not in module.__file__:
				raise ValueError(f"Invalid module requested for SWD: {module.__file__}")

			for key in dir(module):
				obj = getattr(module, key)
				if inspect.isclass(obj):
					if issubclass(obj, Module) and obj != Module:
						mod = obj()
						self.__modules[mname] = mod
						return (mod, mname, nested_template)
		else:
			raise ValueError(f"Could not load SWD module {path}")

class Module:
	templates = []
	scripts = []
	style = []

	def __init__(self):
		self.__mod_dir = pathlib.Path(sys.modules[type(self).__module__].__file__).parent
		self.__templates = ["template"] + self.templates
		self.__scripts = ["scripts"] + self.scripts
		self.__style = ["style"] + self.style

		self.__templates = map_dirs(self.__mod_dir, self.__templates)
		self.__scripts = map_dirs(self.__mod_dir, self.__scripts)
		self.__style = map_dirs(self.__mod_dir, self.__style)

		self.__loader = jinja2.FileSystemLoader(self.__templates)

	@property
	def loader(self):
		return self.__loader

	def get_file_path(self, path):
		return f"{self.__mod_dir}/{path}"

__all__ = [
	"Module",
	"ModuleLoader",
]