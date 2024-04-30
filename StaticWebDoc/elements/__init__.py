from typing import Self
from typing import Type

from .. import utils

class Element:
	def __init__(self, tagname: str, fname: str, position: (int, int), *children, **kwds):
		self.__tagname = tagname
		self.__fname = fname
		self.__pos = position
		
		self.__children = list(children)
		self.__attrs = dict(kwds)
		self.__parent = None
		self.__ended = False

	def end(self):
		self.__ended = True

	@property
	def fname(self):
		return self.__fname

	@property
	def pos(self):
		return self.__pos	

	@property
	def tagname(self) -> str:
		return self.__tagname

	@property
	def attrs(self):
		return self.__attrs
	

	@property
	def parent(self) -> Self | None:
		return self.__parent
	
	@property
	def children(self) -> [Self]:
		return self.__children
	

	def append(self, child: Self):
		if child is not None:
			child.__parent = self
			self.__children.append(child)

	def compile(self, outfile):
		pass

	@property
	def formatted_attrs(self):
		return ' '.join(["{0}='{1}'".format(k, v) for (k, v) in self.__attrs.items()])


	def print(self, indent=0):
		if len(self.__children) == 0:
			print(f"{'    '*indent}<{self.__tagname} {self.formatted_attrs}/>")
		else:
			print(f"{'    '*indent}<{self.__tagname} {self.formatted_attrs}>")

			for c in self.__children:
				c.print(indent=indent+1)

			print(f"{'    '*indent}</{self.__tagname}>")


class Document(Element):
	def __init__(self, fname: str, position: (int, int), *children, **kwds):
		super().__init__('document', fname, position, *children, **kwds)

class TextElement(Element):
	def __init__(self, data, fname: str, position: (int, int), *children, **kwds):
		super().__init__('text', fname, position, **kwds)
		self.__text = data

	def append(self, _):
		pass

	def compile(self, outfile):
		outfile.write(self.__text)

	def concat(self, text):
		self.__text += text

	def print(self, indent=0):
		print(self.__text)


class CharRefElement(Element):
	def __init__(self, data, fname: str, position: (int, int), *children, **kwds):
		super().__init__('charref', fname, position, *children, **kwds)
		self.__data = data

	def compile(self, outfile):
		outfile.write(f"&#{self.__data};")

	def append(self, _):
		pass