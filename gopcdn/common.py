CDN = 'gopcdn'

ENABLE = 1
DISENABLE = 0

CACHESETNAME = 'gopcdn-resource-caches'
CACHETIME = 600


DOMAIN = {'type': 'string', 'format': 'hostname'}


DOMAINS = {'type': 'array', 'items': DOMAIN, 'description': 'domain hostname list'}

PATHPATTERN = '^[a-z0-9]+?(?!.*?/[\.]{1,}/)([a-z0-9\.\-_/])+?[a-z0-9]+?$'

FILEINFOSCHEMA = {
    'type': 'object',
    'required': ['md5', 'size', 'filename'],
    'properties': {
        "size": {'type': 'integer', 'minimum': 30},
        'md5': {'type': 'string', 'format': 'md5'},
        "ext": {'type': 'string'},
        "filename": {'type': 'string', "pattern": PATHPATTERN},
        "overwrite": {'oneOf': [{'type': 'null'},
                                {'type': 'string', "pattern": PATHPATTERN}]}
    }
}