CDN = 'gopcdn'

ENABLE = 1
DISENABLE = 0

DOMAIN = {'type': 'string', 'format': 'hostname'}


DOMAINS = {'type': 'array', 'items': DOMAIN, 'description': 'domain hostname list'}

PATHPATTERN = '^[a-z0-9]+?(?!.*?/[\.]{1,}/)([a-z0-9\.\-_/])+?[a-z0-9]+?$'

FILEINFOSCHEMA = {
    'type': 'object',
    'required': ['crc32', 'md5', 'size'],
    'properties': {
        "size": {'type': 'integer', },
        'crc32': {'type': 'string',
                  'pattern': '^[0-9]+?$'},
        'md5': {'type': 'string', 'format': 'md5'},
        "ext": {'type': 'string'},
        "filename": {'type': 'string', "pattern": PATHPATTERN},
        "overwrite": {'type': 'string', "pattern": PATHPATTERN},
    }
}