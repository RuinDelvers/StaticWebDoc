from . import Element
from .. import parser
from .. import project

class IncludeElement(Element):
	def __init__(self, fname: str, position: (int, int), *children, **kwds):
		super().__init__('include', fname, position, *children, **kwds)

		if 'src' in self.attrs:

			sub_file = parser.Parser(
				project.PROJECT.get_doc_path(self.attrs['src']),
				docdef=True)
			sub_file.parse()
			sub_file.validate()

			self.append(sub_file.ast)


