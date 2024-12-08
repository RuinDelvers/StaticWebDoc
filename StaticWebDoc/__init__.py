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
DEFAULTE_RENDER_DIR = "render"
DOCUMENT_DIR = "document"
STYLE_DIR = "style"
SCRIPT_DIR = "scripts"
DATA_DIR = "data"
IMAGE_DIR = "images"
CACHE_FILE = "fields.json"
OBJECT_FILE = "objects.json"

CURRENT_RENDERING_PROJECT = None
GLOBAL_PROJECT_TYPES = []
GLOBAL_FUNCTIONS = []
GLOBAL_FILTERS = []

def current_project():
	return CURRENT_RENDERING_PROJECT

class Markupable:
	""" Marker class to determine whether or not to call markup on when rendering."""

	def markup(self):
		raise NotImplementedError(f"markup() not implemented for {type(self).__name__}")

	def __str__(self):
		return self.markup()

def _is_class_template(path):
	values = map(lambda x: x[0] == x[1], zip(path.suffixes, ('.class', '.jinja')))

	return all(values)

def _is_renderable_template(path):
	if type(path) == str:
		path = pathlib.Path(path)
	return not _is_class_template(path)

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
	output: str = DEFAULTE_RENDER_DIR
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
		self.__docroot = self.__output/self.document_dir
		self.__dataroot = self.__output/self.data_dir
		self.__cache_file = self.__dataroot/self.cache_file
		self.__object_file = self.__dataroot/self.object_file

		if self.env is None:
			self.env = CustomEnvironment(
				loader=jinja2.FileSystemLoader(self.__input),
				autoescape=jinja2.select_autoescape(),
				extensions=[
					extensions.FragmentCacheExtension,
					extensions.EmbeddedDataExtension,
					extensions.EmbeddedDataSectionExtension]
					+ self.exts)

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
		self.add_global("get_field", self.__get_field)
		self.add_global("link_to", self.link_to_topic)
		self.add_global("template_name", template_to_name)

		self.add_global("style", _style)
		self.add_global("link", _link)
		self.add_global("markup", lambda text: _get_markup(text))
		self.add_global(self.pop_context_data.__name__, self.pop_context_data)
		self.add_global(self.set_context_data.__name__, self.set_context_data)
		self.add_global(self.get_context_data.__name__, self.get_context_data)
		self.add_global(self.current_template.__name__, self.current_template)
		self.add_global(self.env_data.__name__, self.env_data)

		for key, value in self.global_vars.items():
			self.add_global(key, value)

		for obj in GLOBAL_PROJECT_TYPES:
			self.add_global(obj.__name__, obj)

		for obj in GLOBAL_FUNCTIONS:
			if isinstance(obj, tuple):
				name, fn = obj
				self.add_global(name, fn)
			else:
				self.add_global(obj.__name__, obj)

		for obj in GLOBAL_FILTERS:
			if isinstance(obj, tuple):
				name, fn = obj
				self.env.filters[name] = fn
			else:
				self.env.filters[obj.__name__] = obj



	def link_to_topic(self, template_name, display=None):
		inpath = pathlib.Path(template_name)

		if inpath.suffix != TEMPLATE_EXTENSION:
			template_name += ".jinja"

		if display is None:
			display = self.__get_field(template_name, "name")

		path = self.__template_to_outpath(template_name)

		return jinja2.filters.Markup(f"<a href={path}>{display}</a>")

	def __get_field(self, template, key):
		cache = self.env.get_cache()

		checkpath = pathlib.Path(template)

		if checkpath.suffix != TEMPLATE_EXTENSION:
			template += TEMPLATE_EXTENSION

		if template not in cache:
			self.__render_inner(template)

		if template not in cache:
			raise ValueError(f"Template '{template}' does not have key '{key}'")

		if key in cache[template]:
			return cache[template][key].strip()
		else:
			raise ValueError(f"Template '{template}' does not have key '{key}'")

	def __path_to_template(self, path):
		return str(path.relative_to(self.__input).as_posix())

	def __template_to_outpath(self, template_name):
		path = pathlib.Path(self.__docroot)/template_name
		path = path.with_suffix(OUTPUT_EXTENSION)

		# Need to make sure that this is considered from the root of the website.
		return f"/document/{path.relative_to(self.__docroot)}"

	def renderable_templates(self):
		if len(self.__renderable_templates) == 0:
			path = pathlib.Path(self.__input)

			self.__renderable_templates = list(self.env.list_templates(filter_func=_is_renderable_template))

		return self.__renderable_templates

	def filtered_templates(self):
		for temp in self.renderable_templates():
			if all(map(lambda x: x(self.__input/temp, self.output_file(temp)), self.__filters)):
				yield temp

	def output_file(self, template_name):
		path = self.__docroot/template_name
		path = path.with_suffix(".html")

		return path

	def __render_inner(self, template_name):
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
		data = self.env.get_data()
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

	def __clean_render_dir(self):
		if self.__docroot.exists():
			self.logger.normal(f'- Removing directory: {self.__docroot}')
			shutil.rmtree(self.__docroot)

		if self.__dataroot.exists():
			self.logger.normal(f'- Removing directory: {self.__dataroot}')
			shutil.rmtree(self.__dataroot)

	def clean(self):
		self.__clean_render_dir()

	def __load_data(self):
		if self.__cache_file.exists():
			with open(self.__cache_file, 'r') as read:
				self.env.load_cache(orjson.loads(read.read()))

		if self.__object_file.exists():
			with open(self.__object_file, 'r') as read:
				self.env.load_data(orjson.loads(read.read()))

	def __filter_data(self):
		for temp in self.filtered_templates():
			self.env.clear_cache(key=temp)
			self.env.clear_data(key=temp)

	def __write_data(self):
		self.__dataroot.mkdir(exist_ok=True, parents=True)

		with open(self.__cache_file, 'wb') as output:
			value = orjson.dumps(self.env.get_cache(), option=orjson.OPT_INDENT_2)
			output.write(value)

		with open(self.__object_file, 'wb') as output:
			encoder = extensions.JSONEncoder()
			value = orjson.dumps(
				self.env.get_data(),
				option=self.json_flags,
				  default=encoder)
			output.write(value)


	def pre_process(self):
		pass

	def post_process(self):
		pass

	def render(self):
		global CURRENT_RENDERING_PROJECT

		if CURRENT_RENDERING_PROJECT is not None:
			raise ValueError("Another project is already rendering.")

		CURRENT_RENDERING_PROJECT = self
		#self.__load_data()
		#self.__filter_data()
		self.__clean_render_dir()
		self.pre_process()

		for template in self.renderable_templates():
			self.__render_inner(template)

		self.__rendered_templates = set()
		self.__renderable_templates = []

		self.__write_data()
		self.post_process()

		CURRENT_RENDERING_PROJECT = None

__all__ = [
	"Project",
	"proj_fn",
	"proj_type",
	"proj_filter",
	"Markupable",
	"current_project"
]
