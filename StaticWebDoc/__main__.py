import StaticWebDoc
import importlib
import importlib.util
import os
import pathlib
import argparse
import traceback
import jinja2
from termcolor import colored
from . import exceptions
from .logging import DEFAULT as logger

class App:
	def __init__(self):
		self.__parser = argparse.ArgumentParser(
			prog="StaticWebDoc",
			description="Compiles HTML template files into a static web site.")

		self.__add_arguments()
		self.__args = self.__parser.parse_args()
		self.__directory = pathlib.Path(self.__args.project_dir[0])

	def __add_arguments(self):
		self.__parser.add_argument(
			"project_dir", type=str, nargs=1, default=os.getcwd())
		self.__parser.add_argument(
			"--clean", "-c", action="store_true")
		self.__parser.add_argument(
			"--init", action="store_true")
		self.__parser.add_argument(
			"--package", action="store_true")
		self.__parser.add_argument(
			"--server", action="store_true", help="Starts up a testing HTTP server. Do not use in production.")

	def run(self):
		if self.args.server:
			self.__server()
		elif self.args.init:
			self.__init_project()
		elif self.args.clean:
			self.__get_project()
			logger.normal(f"- Clearing output directory: {type(self.__project).__name__}")
			self.__project.clean()
		elif self.args.package:
			self.__get_project()
			logger.normal(f"- Packaging project: {type(self.__project).__name__}")
			self.__project.package()
		else:
			self.__get_project()
			self.__project.render()
			logger.normal("[Finished]", "green")

	@property
	def proj_dir(self):
		return self.__directory

	@property
	def args(self):
		return self.__args

	def __server(self):
		import StaticWebDoc.server as serv
		root = pathlib.Path(self.proj_dir)
		serv.main(root)

	def __init_project(self):
		root = pathlib.Path(self.proj_dir).absolute()
		logger.normal(f"Initializing SWD project at {root}")
		StaticWebDoc.initialize_project(root)

	def __get_project(self):
		logger.normal(f"Searching for projects in directory {self.proj_dir}")

		if self.proj_dir.exists():
			logger.normal(f"- Found project file: {self.proj_dir}")

		spec = importlib.util.spec_from_file_location(self.proj_dir.name, self.proj_dir/"__init__.py")
		code = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(code)

		for var in dir(code):
			obj = getattr(code, var)
			if type(obj) == type(StaticWebDoc.Project):
				if obj != StaticWebDoc.Project and issubclass(obj, StaticWebDoc.Project):
					logger.normal(f"- Found project declaration: {obj.__name__}")
					project = obj(self.proj_dir)

					self.__project = project
					return project


if __name__ == '__main__':
	try:
		App().run()
	except jinja2.exceptions.TemplateError as ex:
		logger.error(exceptions.get_jinja_message(ex))
		exit(1)
	except StaticWebDoc.RenderError as ex:
		logger.error(f"\n[Error] {type(ex).__name__}: {ex.message}")
		exit(1)
	except Exception as ex:
		traceback.print_exception(ex)
		logger.error(f"\n[Error] {type(ex).__name__}")
		exit(1)