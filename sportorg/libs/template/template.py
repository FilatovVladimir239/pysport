import base64
import datetime
import gzip
import os

import dateutil.parser
from jinja2 import Environment, FileSystemLoader


def to_hhmmss(value, fmt=None):
    """value = 1/1000 s"""
    if value is None:
        return ""
    if not fmt:
        fmt = "%H:%M:%S"
    dt = datetime.datetime(
        2000,
        1,
        1,
        value // 3600000 % 24,
        (value % 3600000) // 60000,
        (value % 60000) // 1000,
        (value % 1000) * 10,
    )
    return dt.strftime(fmt)


def date(value, fmt=None):
    if not value:
        return ""
    if not fmt:
        fmt = "%d.%m.%Y"
    return dateutil.parser.parse(value).strftime(fmt)


def finalize(thing):
    return thing if thing else ""


def _make_template_env(searchpath):
    if isinstance(searchpath, str):
        searchpath = [searchpath]
    env = Environment(loader=FileSystemLoader(searchpath), finalize=finalize)
    env.filters["tohhmmss"] = to_hhmmss
    env.filters["date"] = date
    env.filters["compress"] = compress
    env.policies["json.dumps_kwargs"]["ensure_ascii"] = False
    return env


def _template_search_paths(path):
    template_dir = os.path.dirname(os.path.abspath(path))
    parent_dir = os.path.dirname(template_dir)
    search_paths = [template_dir]
    if parent_dir and parent_dir not in search_paths:
        search_paths.append(parent_dir)
    return search_paths


def get_text_from_path(path, **kwargs):
    env = _make_template_env(_template_search_paths(path))
    template = env.get_template(os.path.basename(path))
    return template.render(**kwargs)


def compress(data: str) -> str:
    return base64.b64encode(gzip.compress(data.encode())).decode()


def get_text_from_template(searchpath: str, path: str, **kwargs):
    env = _make_template_env(searchpath)
    template = env.get_template(path)

    return template.render(**kwargs)
