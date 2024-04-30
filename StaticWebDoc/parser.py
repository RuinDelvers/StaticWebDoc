import enum

from dataclasses import dataclass
from dataclasses import InitVar
from html.parser import HTMLParser
from typing import Self
from typing import Type

from . import error
from . import elements
from .elements import include

def DEFAULT_TAG_MAP(tag, fname, pos, **kwds): 
	return elements.Element(tag, fname, pos, **kwds)



@dataclass
class ElementSpec:
	name: str
	element: Type[elements.Element]

class BuiltinTags(enum.Enum):
	document = ElementSpec('document', elements.Document)
	include = ElementSpec('include', include.IncludeElement)
	

class Parser(HTMLParser):
	def __init__(self, fname: str, docdef: bool=False):
		super().__init__(convert_charrefs=False)
		self.__fname = fname
		self.__root = None
		self.__current = None
		self.__docdef = docdef

	@property
	def ast(self):
		return self.__root

	def handle_starttag(self, tag, attrs):
		# An issue with enums until 3.12.
		# @TODO update this for 3.12 in the future.
		try:
			tagspec = BuiltinTags[tag]

			# Check to see if we're defining the document class.
			if tagspec is BuiltinTags.document:

				# If the AST is empty, then we only parse it if we're not recursive parsing.
				if self.__root is None:
					if self.__docdef:
						self.reset()
						raise error.RedefinedDocument(self.__fname, self.getpos())
					else:
						self.__append_tag(tagspec, attrs)
				# If the AST wasn't empty, then the document wasn't even defined yet.
				else:
					self.reset()
					raise error.UndefinedDocument(self.__fname, self.getpos())
			else:
				self.__append_tag(tagspec, attrs)
		except KeyError:
			print(f"---- waffles ----: {self.__docdef}")
			print(f"---- waffles ----: {self.__fname}")
			if self.__root is None:
				if self.__docdef:
					self.__append_tag(tag, attrs)
				else:
					self.reset()
					raise error.UndefinedDocument(self.__fname, self.getpos())
			else:
				self.__append_tag(tag, attrs)

	def __append_tag(self, tag, attrs):
		if type(tag) == BuiltinTags:
			if self.__root is None:
				self.__root = tag.value.element(self.__fname, self.getpos(), **dict(attrs))
				self.__current = self.__root
			else:
				t = tag.value.element(self.__fname, self.getpos(), **dict(attrs))
				self.__current.append(t)
				self.__current = t
		elif type(tag) == str:
			# TODO: Setup module structure for custom elements.
			# If we find the tag is control by a custom tag, construct custom element.
			if False:
				pass
			# Otherwise it's likely a default html tag, so just add it as a basic element.
			else:

				if self.__root is None:
					self.__root = DEFAULT_TAG_MAP(tag, self.__fname, self.getpos(), **dict(attrs))
					self.__current = self.__root
				else:
					t = DEFAULT_TAG_MAP(tag, self.__fname, self.getpos(), **dict(attrs))
					self.__current.append(t)
					self.__current = t


	def handle_endtag(self, tag):
		if tag == BuiltinTags.document.value.name:
			self.__current.end()
			self.__current = self.__root
		else:
			if self.__current.tagname == tag:
				self.__current.end()
				self.__current = self.__current.parent
			else:
				raise error.MismatchedTags(
					self.__current.tagname,
					self.__current.fname, 
					self.__current.pos,
					tag,
					self.__fname, 
					self.getpos())
				

	def handle_data(self, data):
		if self.__current is None:
			if len(data.strip()) > 0:
				raise error.UndefinedDocument(self.__fname, self.getpos())			
		else:
			children = self.__current.children

			if len(children) == 0:
				self.__current.append(elements.TextElement(data, self.__fname, self.getpos()))
			else:
				if isinstance(children[-1], elements.TextElement):
					children[-1].concat(data)
				else:
					self.__current.append(elements.TextElement(data, self.__fname, self.getpos()))
			


	def handle_entityref(self, name):
		pass

	def handle_charref(self, name):
		pass

	def handle_comment(self, data):
		pass

	def handle_decl(self, decl):
		pass

	def handle_pi(self, data):
		pass

	def unknown_decl(self, data):
		pass

	def add_handler(self, tagname: str):
		pass

	def parse(self):
		with open(self.__fname, 'r') as file:
			self.feed(file.read())

		return self

	def validate(self):
		pass
	
	