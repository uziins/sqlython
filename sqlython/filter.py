import datetime
import json

def columns(obj, fillable=None, guarded=None):
    if fillable is None:
        fillable = []
    if guarded is None:
        guarded = []

    data = {}
    for key in obj:
        if (not fillable or key in fillable) and (not guarded or key not in guarded):
            data[key] = obj[key]
    return data

def casts(obj, cast=None, reverse=False):
    if cast is None:
        cast = {}

    for field in cast:
        if field in obj:
            value = obj[field]
            try:
                if reverse:
                    if cast[field] == 'json':
                        obj[field] = json.dumps(value) if isinstance(value, (dict, list)) else None
                    elif cast[field] == 'boolean':
                        obj[field] = 1 if isinstance(value, bool) and value else 0
                    elif cast[field] == 'date':
                        obj[field] = value.isoformat() if isinstance(value, datetime.date) else None
                    elif cast[field] in ['number', 'float']:
                        obj[field] = float(value) if isinstance(value, (int, float)) else None
                    elif cast[field] == 'string':
                        obj[field] = str(value) if value is not None else None
                else:
                    if cast[field] == 'json':
                        obj[field] = json.loads(value) if isinstance(value, str) and value else None
                    elif cast[field] == 'boolean':
                        if isinstance(value, bool):
                            obj[field] = value
                        elif isinstance(value, int):
                            obj[field] = bool(value)
                        elif isinstance(value, str) and value.isdigit():
                            obj[field] = bool(int(value))
                        else:
                            obj[field] = None
                    elif cast[field] == 'date':
                        obj[field] = datetime.datetime.fromisoformat(value) if isinstance(value, str) else None
                    elif cast[field] in ['number', 'float']:
                        if isinstance(value, (int, float)):
                            obj[field] = float(value)
                        elif isinstance(value, str) and value.replace('.', '', 1).isdigit():
                            obj[field] = float(value)
                        else:
                            obj[field] = None
                    elif cast[field] == 'string':
                        obj[field] = str(value) if value is not None else None
            except (ValueError, TypeError, AttributeError) as e:
                print(f"Warning: Failed to cast field '{field}' with value '{value}' as '{cast[field]}'. Error: {e}")
                obj[field] = None
    return obj
