from goperation.common import FILEINFOSCHEMA

CDN = 'gopcdn'

ENABLE = 1
DISENABLE = 0

CACHESETNAME = 'gopcdn-resource-caches'
CACHETIME = 600

DOMAIN = {'type': 'string', 'format': 'hostname'}

DOMAINS = {'type': 'array', 'items': DOMAIN, 'description': 'domain hostname list'}