from flask import request


def int_arg(name: str, default=None, source=None):
    source = source if source is not None else request.args
    try:
        return int(source.get(name, ""))
    except (TypeError, ValueError):
        return default
