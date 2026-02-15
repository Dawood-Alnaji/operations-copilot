import os
from jinja2 import Environment, FileSystemLoader


def render_markdown(template_name: str, context: dict, template_dir: str) -> str:
    absolute_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), template_dir))
    env = Environment(loader=FileSystemLoader(absolute_dir))
    template = env.get_template(template_name)
    return template.render(context)