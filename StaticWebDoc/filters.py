import pathlib
import os

class BaseFilter:
	def __init__(self, project):
		self.__project = project

	@property
	def project(self):
		return self.__project

	def __call__(self, template, rendered):
		raise NotImplementedError("")

class LastModified(BaseFilter):
	def __call__(self, template, rendered):
		return not os.path.isfile(rendered) or os.path.getmtime(template) > os.path.getmtime(rendered)