import datetime
import json

def columns(obj, fillable=None, guarded=None):
    if fillable is None:
        fillable = []
    if guarded is None:
        guarded = []

    data = {}
    for key in obj:
        if (len(fillable) > 0 and key in fillable) or (len(guarded) > 0 and key not in guarded):
            data[key] = obj[key]
    return data

def casts(obj, cast=None, reverse=False):
    if cast is None:
        cast = {}

    for field in cast:
        if field in obj:
            if reverse:
                if cast[field] == 'json':
                    obj[field] = json.dumps(obj[field])
                elif cast[field] == 'boolean':
                    obj[field] = 1 if obj[field] else 0
                elif cast[field] == 'date':
                    obj[field] = obj[field].isoformat()
                elif cast[field] == 'number':
                    obj[field] = float(obj[field])
                elif cast[field] == 'string':
                    obj[field] = str(obj[field])
                elif cast[field] == 'float':
                    obj[field] = float(obj[field])
            else:
                if cast[field] == 'json':
                    obj[field] = json.loads(obj[field])
                elif cast[field] == 'boolean':
                    obj[field] = bool(obj[field])
                elif cast[field] == 'date':
                    obj[field] = datetime.datetime.fromisoformat(obj[field])
                elif cast[field] == 'number':
                    obj[field] = float(obj[field])
                elif cast[field] == 'string':
                    obj[field] = str(obj[field])
                elif cast[field] == 'float':
                    obj[field] = float(obj[field])
    return obj