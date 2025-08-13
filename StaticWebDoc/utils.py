import jinja2.filters

def style(path: str) -> str:
	if path.startswith("@"):
		module, path = path[1:].split("/", 1)
		return jinja2.filters.Markup(f'<link rel="stylesheet" type="text/css" href="/@{module}/style/{path}">')
	else:
		return jinja2.filters.Markup(f'<link rel="stylesheet" type="text/css" href="/style/{path}">')

def script(path: str, type="module", defer=False) -> str:
	if path.startswith("@"):
		module, path = path[1:].split("/", 1)
		return jinja2.filters.Markup(f'<script src="/@{module}/scripts/{path}" type="{type}" {'defer' if defer else ''}></script>')
	else:
		return jinja2.filters.Markup(f'<script src="/scripts/{path}" type="{type}" {'defer' if defer else ''}></script>')