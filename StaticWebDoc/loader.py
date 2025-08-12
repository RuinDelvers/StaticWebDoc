import jinja2
import importlib
import inspect

import StaticWebDoc.modules as modules

class CustomLoader(jinja2.FileSystemLoader):
	def __init__(self, searchpath, encoding="utf-8", followlinks=False):
		super().__init__(searchpath, encoding=encoding, followlinks=followlinks)

		self.__loader = modules.ModuleLoader()

	def get_source(self, env, template: str):
		if template.startswith("@"):
			module, mname, nested_template = self.__loader.load_module(template)

			try:
				return module.loader.get_source(env, nested_template)
			except jinja2.exceptions.TemplateNotFound as ex:
				raise jinja2.exceptions.TemplateNotFound(f"@{mname} -> {ex.name}")

		else:
			return super().get_source(env, template)





