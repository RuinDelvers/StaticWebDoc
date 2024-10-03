import StaticWebDoc
import importlib
import importlib.util
import os
import pathlib
import argparse
import sys
import traceback
import jinja2

class App:
	def __init__(self):
		self.__parser = argparse.ArgumentParser(
			prog="StaticWebDoc",
			description="Compiles HTML template files into a static web site.")

		self.__add_arguments()

	def __add_arguments(self):
		self.__parser.add_argument(
			"project_dir", type=str, nargs="*", default=os.getcwd())
		self.__parser.add_argument(
			"--clean", "-c", action="store_true")

	def run(self):
		args = self.__parser.parse_args()

		if len(args.project_dir) == 0:
			root = pathlib.Path(os.getcwd())
			self.__run_single(root, args)
		else:
			for p in args.project_dir:
				root = pathlib.Path(p)
				self.__run_single(root, args)

		

	def __run_single(self, root, args):
		print(f"Searching for projects in directory {root}")

		projectfile = root/"project.py"

		if projectfile.exists():
			print(f"- Found project file: {projectfile}")

		spec = importlib.util.spec_from_file_location(
			f"StaticWebDoc.{projectfile.stem}",
			projectfile)
		code = importlib.util.module_from_spec(spec)
		spec.loader.exec_module(code)

		for var in dir(code):
			obj = getattr(code, var)
			if type(obj) == type(StaticWebDoc.Project):
				if obj != StaticWebDoc.Project and issubclass(obj, StaticWebDoc.Project):
					print(f"- Found project declaration: {obj.__name__}")
					project = obj(root)
					if args.clean:
						print(f"- Clearing output directory: {obj.__name__}")
						project.clean();
					else:
						project.render()


if __name__ == '__main__':
	try:
		App().run()
	except jinja2.TemplateNotFound as ex:
		print(f"\n[Error] {type(ex).__name__}: {ex.message}")
		exit(1)
	except jinja2.TemplateAssertionError as ex:
		print(f"\n[Error] {type(ex).__name__}: {ex.message}")
		exit(1)
	except Exception as ex:
		print(f"\n[Error] {type(ex).__name__}")
		traceback.print_exception(ex)		
		exit(1)
