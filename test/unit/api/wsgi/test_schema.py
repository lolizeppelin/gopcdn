from simpleutil.config import cfg

from gopcdn import common

# CONF = cfg.CONF
# CONF(project='test',  default_config_files=[])
# endpoint_group = cfg.OptGroup(common.CDN)
# CONF.register_group(endpoint_group)

from simpleutil.utils import jsonutils

NOTIFYSCHEMA = {
    'oneOf': [
        {'type': 'object',
         'required': ['method', 'target', 'ctxt', 'msg'],
         'properties': {
             'target': {'type': 'object',
                        'required': ['topic', 'namespace'],
                        'properties': {
                            'exchange': {'oneOf': [{'type': 'null'}, {'type': 'string'}]},
                            'topic': {'type': 'string'},
                            'namespace': {'oneOf': [{'type': 'null'}, {'type': 'string'}]},
                            'version': {'type': 'string'},
                            'server': {'oneOf': [{'type': 'null'}, {'type': 'string'}]},
                            'fanout': {'oneOf': [{'type': 'null'}, {'type': 'string'}]}}
                        },
             'method': {'type': 'string', 'enum': ['cast', 'call', 'notify']},
             'ctxt': {'type': 'object'},
             'msg': {'type': 'object'},
             'timeout': {'type': 'integer', 'minimum': 5}}
         },
        {'type': 'object',
         'required': ['method', 'action'],
         'properties': {
             'method': {'type': 'string',
                        'enum': ['GET', 'DELETE', 'POST', 'PUT', 'HEAD', 'PATCH', 'OPTIONS']},
             'action': {'type': 'string'},
             'body': {'oneOf': [{'type': 'null'}, {'type': 'object'}]},
             'headers': {'oneOf': [{'type': 'null'}, {'type': 'object'}]},
             'params': {'oneOf': [{'type': 'null'}, {'type': 'object'}]},
             'timeout': {'oneOf': [{'type': 'null'}, {'type': 'integer', 'minimum': 3, 'maxmum': 30}]}}
         }
    ]
}

UPLOADSCHEMA = {
    'type': 'object',
    'required': ['fileinfo'],
    'properties': {
        'impl': {'type': 'string'},
        'auth': {'oneOf': [{'type': 'object'}, {'type': 'null'}]},
        'timeout': {'type': 'integer', 'minimum': 30, 'mixmum': 3600},
        'notify': {'oneOf': [{'type': 'object'}, {'type': 'null'}]},
        'fileinfo': common.FILEINFOSCHEMA,
    }
}

data = {'fileinfo': {'ext': 'dat', 'md5': 'd2dec017d3573b6d4a67bec725c9dcbc', 'size': 162926,
                     'overwrite': None,
                     'filename': '690794aac8d54887a4e9fa13606a08ad.dat'},
        'notify': {'fail': {'body': {'status': 'MISSED'},
                            'action': '/gogamechen1/objfiles/56e5e13c-8edf-4f4d-9c33-debe61a36868',
                            'method': 'DELETE'},
                   'success': {'body': {'status': 'FILEOK'},
                               'action': '/files/56e5e13c-8edf-4f4d-9c33-debe61a36868',
                               'method': 'PUT'}},
        'auth': None, 'timeout': 30, 'impl': 'websocket'}

jsonutils.schema_validate(data, UPLOADSCHEMA)
