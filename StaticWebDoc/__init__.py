import jinja2
import pathlib
import shutil
import orjson

import jinja2.ext
import jinja2.filters

import StaticWebDoc.extensions as extensions
import StaticWebDoc.filters as filters
import StaticWebDoc.logging as logging

from StaticWebDoc.environment import CustomEnvironment
from StaticWebDoc.exceptions import RenderError
from termcolor import colored

TEMPLATE_EXTENSION = ".jinja"
OUTPUT_EXTENSION = ".html"
CLASS_EXTENSION = ".class"

DEFAULT_TEMPLATE_DIR = "template"
DEFAULT_RENDER_DIR = "render"
DEFAULT_MODULE_DIR = "modules"
DOCUMENT_DIR = "document"
STYLE_DIR = "style"
SCRIPT_DIR = "scripts"
DATA_DIR = "data"
IMAGE_DIR = "images"
CACHE_FILE = "fields.json"
OBJECT_FILE = "objects.json"

# Global types/functions that have been added to be made available for use.
GLOBAL_PROJECT_TYPES = []
GLOBAL_FUNCTIONS = []
GLOBAL_FILTERS = []

class Markupable:
	""" Marker class to determine whether or not to call markup on when rendering."""

	def markup(self):
		raise NotImplementedError(f"markup() not implemented for {type(self).__name__}")

	def __str__(self):
		return self.markup()



def _style(path):
	return jinja2.filters.Markup(f'<link rel="stylesheet" type="text/css" href="/style/{path}">')

def _link(location, display_text, class_type=""):
	path_check = pathlib.Path(location)
	if path_check.suffix != OUTPUT_EXTENSION:
		location += OUTPUT_EXTENSION

	return jinja2.filters.Markup(f'<a href="/document/{location}" class="{class_type}"> {display_text} </a>')

def template_to_name(template_name, root=None, base_only=False):
	p = pathlib.Path(template_name)

	if root is None:
		if base_only:
			return p.with_suffix("").name
		else:
			return p.with_suffix("").as_posix()
	else:
		if base_only:
			return p.relative_to(root).with_suffix("").name
		else:
			return p.relative_to(root).with_suffix("").as_posix()

def _get_markup(value):
	if isinstance(value, Markupable):
		return jinja2.filters.Markup(value.markup())
	else:
		return jinja2.filters.Markup(value)

def proj_fn(name):
	if type(name) == str:
		def inner(fn):
			GLOBAL_FUNCTIONS.append((name, fn))
			return fn
		return inner
	else:
		GLOBAL_FUNCTIONS.append(name)
		return name

def proj_filter(name):
	if type(name) == str:
		def inner(fn):
			GLOBAL_FILTERS.append((name, fn))
			return fn
		return inner
	else:
		GLOBAL_FILTERS.append(name)
		return name

def proj_type(value):
	value.is_project_defined_type = True

	GLOBAL_PROJECT_TYPES.append(value)

	return value

class Project:
	source: str = DEFAULT_TEMPLATE_DIR
	output: str = DEFAULT_RENDER_DIR
	modules: str = DEFAULT_MODULE_DIR
	script_dir: str = SCRIPT_DIR
	style_dir: str = STYLE_DIR
	image_dir: str = IMAGE_DIR
	data_dir: str = DATA_DIR
	document_dir: str = DOCUMENT_DIR
	env: jinja2.Environment | None = None
	exts = []
	global_vars = {}
	template_filters = [filters.LastModified]
	logger: logging.Logger = logging.DEFAULT

	json_flags: int = orjson.OPT_INDENT_2

	cache_file = CACHE_FILE
	object_file = OBJECT_FILE

	def __init__(self, root):
		self.__input = pathlib.Path(root)/self.source
		self.__output = pathlib.Path(root)/self.output
		self.__modules = pathlib.Path(root)/self.modules
		self.__docroot = self.__output/self.document_dir
		self.__dataroot = self.__output/self.data_dir
		self.__cache_file = self.__dataroot/self.cache_file
		self.__object_file = self.__dataroot/self.object_file

		if self.env is None:
			self.env = CustomEnvironment(
				loader=jinja2.FileSystemLoader([self.__input]),
				autoescape=jinja2.select_autoescape(),
				extensions=[
					extensions.FragmentCacheExtension,
					extensions.EmbeddedDataExtension,
					extensions.EmbeddedDataSectionExtension]
					+ self.exts)

		self.env.undefined = jinja2.StrictUndefined
		self.env.extend(project_extension="", project=self)

		self.__filters = list(map(lambda x: x(self), self.template_filters))

		self.__init_dirs()
		self.__init_jinja_globals()

		self.__rendered_templates = set()
		self.__renderable_templates = []

		self.init()

		self.__context_data = {}
		self.__render_stack = []



	def init(self):
		pass

	def __init_dirs(self):
		(self.__output/self.script_dir).mkdir(exist_ok=True, parents=True)
		(self.__output/self.image_dir).mkdir(exist_ok=True, parents=True)
		(self.__output/self.style_dir).mkdir(exist_ok=True, parents=True)

	def add_global(self, key, item):
		if key in self.env.globals:
			raise ValueError(f"Globals key already in use: {key}")

		self.env.globals[key] = item

	def __init_jinja_globals(self):
		self.add_global("style_dir", self.style_dir)
		self.add_global("script_dir", self.script_dir)
		self.add_global("image_dir", self.image_dir)
		self.add_global("document_dir", self.document_dir)
		self.add_global("template_name", template_to_name)

		self.add_global("style", _style)
		self.add_global("link", _link)
		self.add_global("markup", _get_markup)
		self.add_global(self.pop_context_data.__name__, self.pop_context_data)
		self.add_global(self.set_context_data.__name__, self.set_context_data)
		self.add_global(self.get_context_data.__name__, self.get_context_data)
		self.add_global(self.current_template.__name__, self.current_template)
		self.add_global(self.env_data.__name__, self.env_data)

		for key, value in self.global_vars.items():
			self.add_global(key, value)

		for gtype in GLOBAL_PROJECT_TYPES:
			gtype.project = property(lambda _: self)
			self.add_global(gtype.__name__, gtype)

		for fn in GLOBAL_FUNCTIONS:
			if isinstance(fn, tuple):
				name, bound = fn
				self.add_global(name, bound)
			else:
				self.__add_proj_fn(fn.__name__, fn)

		for obj in GLOBAL_FILTERS:
			if isinstance(obj, tuple):
				name, fn = obj
				self.env.filters[name] = fn
			else:
				self.env.filters[obj.__name__] = obj

		# After extensions have been applied, we search through extended objects to see if any of them
		# have callables. If so we add them as global callable functions.
		for v in dir(self.env):
			obj = getattr(self.env, v)
			if isinstance(obj, extensions.HasCallables):
				for name, call in obj.get_callables().items():
					self.add_global(name, call)

	def __add_proj_fn(self, name, fn):
		self.add_global(name, lambda *args, **kwds: fn(self, *args, **kwds))

	def template_to_outpath(self, template_name):
		path = pathlib.Path(self.__docroot)/template_name
		path = path.with_suffix(OUTPUT_EXTENSION)

		# Need to make sure that this is considered from the root of the website.
		return f"/document/{path.relative_to(self.__docroot)}"

	def is_renderable_template(self, template):
		if type(template) == str:
			path = pathlib.Path(template)

		return path.suffixes == [TEMPLATE_EXTENSION] and not pathlib.Path(template).is_relative_to(self.__modules)

	def renderable_templates(self):
		if len(self.__renderable_templates) == 0:
			self.__renderable_templates = list(self.env.list_templates(filter_func=self.is_renderable_template))

		return self.__renderable_templates

	def filtered_templates(self):
		for temp in self.renderable_templates():
			if all(map(lambda x: x(self.__input/temp, self.output_file(temp)), self.__filters)):
				yield temp

	def output_file(self, template_name):
		path = self.__docroot/template_name
		path = path.with_suffix(".html")

		return path

	def request_render(self, template_name):
		if template_name in self.__rendered_templates:
			return

		path = self.output_file(template_name)
		path.parent.mkdir(exist_ok=True, parents=True)

		with open(str(path), 'w') as output:
			self.__render_stack.append(template_name)
			self.logger.normal(f"[Render] {template_name}", "blue")

			did_render = False

			try:
				template = self.env.get_template(template_name)
			except jinja2.TemplateNotFound as ex:
				raise RenderError(template_name, ex)

			try:
				rendered_data = template.render()
			except (jinja2.TemplateAssertionError, jinja2.exceptions.UndefinedError) as ex:
				raise RenderError(template_name, ex)

			output.write(rendered_data)

			self.__rendered_templates.update({template_name})
			self.__render_stack.pop()

	def push_context_data(self, context_name, value):
		if context_name in self.__context_data:
			self.__context_data[context_name].append(value)
		else:
			self.__context_data[context_name] = [value]

	def pop_context_data(self, context_name):
		if context_name in self.__context_data:
			self.__context_data[context_name].pop()
		else:
			raise ValueError(f"Context data does not exist for key {context_name}")

	def set_context_data(self, context_name, value):
		if context_name in self.__context_data:
			self.__context_data[context_name][-1] = value
		else:
			self.__context_data[context_name] = [value]

	def get_context_data(self, context_name):
		if context_name in self.__context_data:
			return self.__context_data[context_name][-1]
		else:
			raise ValueError(f"Context data does not exist for key {context_name}")

	def current_template(self):
		return self.__render_stack[-1]

	def env_data(self, env_key, key=None, default=None, template=None):
		data = self.env.embedded_data
		ctemp = template_to_name(self.current_template()) if template is None else template

		if ctemp in data:
			envs = data[ctemp]
			if env_key in envs:
				env_data = envs[env_key]
				if key is not None:
					if key in env_data:
						return env_data[key]
				else:
					return env_data

		return default

	@property
	def output_dir(self):
		return self.__output

	@property
	def input_dir(self):
		return self.__input

	def clean(self):
		if self.__docroot.exists():
			self.logger.normal(f'- Removing directory: {self.__docroot}')
			shutil.rmtree(self.__docroot)

		if self.__dataroot.exists():
			self.logger.normal(f'- Removing directory: {self.__dataroot}')
			shutil.rmtree(self.__dataroot)

	"""
	def __load_data(self):
		if self.__cache_file.exists():
			with open(self.__cache_file, 'r') as read:
				self.env.load_cache(orjson.loads(read.read()))

		if self.__object_file.exists():
			with open(self.__object_file, 'r') as read:
				self.env.load_data(orjson.loads(read.read()))
	"""

	def __write_data(self):
		self.__dataroot.mkdir(exist_ok=True, parents=True)

		for v in dir(self.env):
			obj = getattr(self.env, v)
			if isinstance(obj, extensions.DataExtensionObject):
				obj.write(self.__dataroot)


	def pre_process(self):
		pass

	def post_process(self):
		pass

	def render(self):
		global CURRENT_RENDERING_PROJECT

		CURRENT_RENDERING_PROJECT = self
		self.clean()
		self.pre_process()

		for template in self.renderable_templates():
			self.request_render(template)

		self.__rendered_templates = set()
		self.__renderable_templates = []

		self.__write_data()
		self.post_process()

__all__ = [
	"Project",
	"proj_fn",
	"proj_type",
	"proj_filter",
	"Markupable",
]
