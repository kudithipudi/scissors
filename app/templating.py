"""Shared Jinja2Templates instance and URL helpers used by all routers.

We deliberately do NOT set FastAPI's `root_path=` constructor argument.
Nginx strips the `/scissors` prefix before proxying to this app (see
nginx's `rewrite ^/scissors(/.*)$ $1 break;`), so the ASGI app always sees
un-prefixed paths. Starlette's `root_path` machinery assumes the opposite
(that `path` still *contains* the prefix), and forcing it corrupts internal
routing for nested mounts (e.g. the /static StaticFiles mount ends up
looking for files under an extra "static/" segment and 404s). Instead, we
build correctly-prefixed absolute URLs for browser-facing links ourselves,
via `build_url()` below.
"""
from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates
from jinja2 import pass_context

from app.config import settings

templates = Jinja2Templates(directory=str(Path(__file__).resolve().parent / "templates"))


def build_url(request: Request, name: str, **path_params) -> str:
    """Build an absolute URL for a named route, prefixed with ROOT_PATH."""
    url = request.url_for(name, **path_params)
    if settings.ROOT_PATH:
        url = url.replace(path=settings.ROOT_PATH + url.path)
    return str(url)


@pass_context
def _url_for(context, name: str, /, **path_params) -> str:
    return build_url(context["request"], name, **path_params)


# Override Jinja2Templates' default `url_for` global (which just calls
# request.url_for with no prefix) so every `{{ url_for(...) }}` in templates
# comes out correctly prefixed with ROOT_PATH.
templates.env.globals["url_for"] = _url_for

# Exposes settings.SITE_LINK_URL / SITE_LINK_LABEL etc. to every template.
templates.env.globals["settings"] = settings
