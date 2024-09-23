import StaticWebDoc
import importlib
import os
import pathlib

root = pathlib.Path(os.getcwd())

print(f"Searching for projects in directory {root}")

projectfile = root/"project.py"

if projectfile.exists():
	print(f"Found project file: {projectfile}")

code = importlib.import_module("project")

for var in dir(code):
	obj = getattr(code, var)
	if type(obj) == type(StaticWebDoc.Project):
		if obj != StaticWebDoc.Project and issubclass(obj, StaticWebDoc.Project):
			print(f"Found project declaration: {obj.__name__}")
			project = obj(root)
			project.render()