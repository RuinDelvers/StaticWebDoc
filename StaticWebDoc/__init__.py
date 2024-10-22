import jinja2
import pathlib
import shutil

from StaticWebDoc.environment import CustomEnvironment
from StaticWebDoc.extensions import FragmentCacheExtension
from StaticWebDoc.exceptions import RenderError
from pathlib import Path

TEMPLATE_EXTENSION = ".jinja"
OUTPUT_EXTENSION = ".html"
CLASS_EXTENSION = ".class"

DEFAULT_TEMPLATE_DIR = "template"
DEFAULTE_RENDER_DIR = "render"
DOCUMENT_DIR = "document"
STYLE_DIR = "style"
SCRIPT_DIR = "scripts"
IMAGE_DIR = "images"
CACHE_FILE = "variables.json"

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

def _template_name(template_name, root=None, base_only=False):
	p = pathlib.Path(template_name)

	if root is None:
		if base_only:
			return p.with_suffix("").name
		else:
			return p.with_suffix("")
	else:
		if base_only:
			return p.relative_to(root).with_suffix("").name
		else:
			return p.relative_to(root).with_suffix("")


def proj_fn(name):
	if type(name) == str:
		def inner(fn):
			fn.decorator = proj_fn
			fn.project_fn_name = name
			return fn
		return inner
	else:
		name.decorator = proj_fn
		name.project_fn_name = name.__name__
		return name


class Project:
	source: str = DEFAULT_TEMPLATE_DIR
	output: str = DEFAULTE_RENDER_DIR
	script_dir: str = SCRIPT_DIR
	style_dir: str = STYLE_DIR
	image_dir: str = IMAGE_DIR
	document_dir: str = DOCUMENT_DIR
	env: jinja2.Environment | None = None

	def __init__(self, root):
		self.__input = pathlib.Path(root)/self.source
		self.__output = pathlib.Path(root)/self.output
		self.__docroot = self.__output/self.document_dir

		if self.env is None:
			self.env = CustomEnvironment(
				loader=jinja2.FileSystemLoader(self.__input),
				autoescape=jinja2.select_autoescape(),
				extensions=[FragmentCacheExtension])

		self.__init_dirs()
		self.__init_jinja_callbacks()

		self.__rendered_templates = set()
		self.__renderable_templates = set()

		self.init()

		self.__context_data = {}

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

	def __init_jinja_callbacks(self):
		self.add_global("style_dir", self.style_dir)
		self.add_global("script_dir", self.script_dir)
		self.add_global("image_dir", self.image_dir)
		self.add_global("document_dir", self.document_dir)
		self.add_global("get_field", self.__get_field)
		self.add_global("link_to", self.__link_to_topic)
		self.add_global("template_name", _template_name)

		self.add_global("style", _style)
		self.add_global("link", _link)
		self.add_global("markup", lambda text: jinja2.filters.Markup(text))		

		for field_name in dir(self):
			obj = getattr(self, field_name)
			if hasattr(obj, "decorator") and obj.decorator == proj_fn:
				self.add_global(obj.project_fn_name, obj)

	

	def __link_to_topic(self, template_name, display=None):
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

			self.__renderable_templates = set(self.env.list_templates(filter_func=_is_renderable_template))

		return self.__renderable_templates

	def __render_inner(self, template_name):
		if template_name in self.__rendered_templates:
			return

		path = self.__docroot/template_name
		path = path.with_suffix(".html")
		path.parent.mkdir(exist_ok=True, parents=True)

		with open(str(path), 'w') as output:
			print(f"[Render] {template_name}")

			try:
				template = self.env.get_template(template_name)
			except jinja2.TemplateNotFound as ex:
				raise RenderError(template_name, ex)

			try:
				rendered_data = template.render()
			except jinja2.TemplateAssertionError as ex:
				raise RenderError(template_name, ex)

			try:
				rendered_data = template.render()
			except jinja2.exceptions.UndefinedError as ex:
				raise RenderError(template_name, ex)

			output.write(rendered_data)

			self.__rendered_templates.update({template_name})

	@proj_fn
	def push_context_data(self, context_name, value):
		if context_name in self.__context_data:
			self.__context_data[context_name].append(value)
		else:
			self.__context_data[context_name] = [value]

		return ""

	@proj_fn
	def pop_context_data(self, context_name):
		if context_name in self.__context_data:
			self.__context_data[context_name].pop()
		else:
			raise ValueError(f"Context data does not exist for key {context_name}")

		return ""


	@proj_fn
	def set_context_data(self, context_name, value):
		if context_name in self.__context_data:
			self.__context_data[context_name][-1] = value
		else:
			self.__context_data[context_name] = [value]

		return ""
		
	@proj_fn
	def get_context_data(self, context_name):
		if context_name in self.__context_data:
			return self.__context_data[context_name][-1]
		else:
			raise ValueError(f"Context data does not exist for key {context_name}")

	@property
	def output_dir(self):
		return self.__output
	
	@property
	def input_dir(self):
		return self.__input

	@property
	def cache_file(self):
		return pathlib.Path(self.__output)/CACHE_FILE
	

	def __clean_render_dir(self):
		if self.__docroot.exists():
			shutil.rmtree(self.__docroot)

		self.cache_file.unlink(missing_ok=True)

	def clean(self):
		self.__clean_render_dir()

	def render(self):
		self.__clean_render_dir()
		work_num = len(self.renderable_templates())

		for template in self.renderable_templates():
			self.__render_inner(template)

		self.env.clear_cache()
		self.__rendered_templates = set()
		self.__renderable_templates = set()

__all__ = [
	"Project",
	"proj_fn"
]