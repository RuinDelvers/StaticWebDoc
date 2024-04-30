import os

from . import parser
from . import project

class Runtime:
	def __init__(self, doc=None, scripts=None, style=None):
		self.__project = project.Project(doc=doc, scripts=scripts, style=style)


	def debug(self):
		self.__project.debug_print()

		for fname in self.__project.doc_files:
			p = parser.Parser(fname)
			p.parse()

			if p.ast is not None:
				p.ast.print()
			else:
				print(f"ast for {os.path.relpath(fname)} was None.")
