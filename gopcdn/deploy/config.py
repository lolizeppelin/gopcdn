from simpleutil.config import cfg
from simpleutil.config import types

CONF = cfg.CONF


deploy_opts = [
    cfg.StrOpt('deployer',
               default='nginx',
               help='Deploy impl, nginx only now'),
    cfg.StrOpt('configdir',
               default='/etc/nginx/gopcdn.d',
               help='Deploy config output path, '
                    'need add this path in to nginx.conf include'),
    cfg.IPOpt('listen',
              default='0.0.0.0',
              help='Default listen ipaddress'),
    cfg.ListOpt('ports',
                item_type=types.Integer(min=1, max=65534),
                default=['80'],
                help='Default listen ports'),
    cfg.StrOpt('character_set',
               default='utf8',
               help='Default character_set'),
    cfg.BoolOpt('autoindex',
                default=True,
                help='Enable autoindex'),
]


def register_opts(group):
    # checkout config for gopcdn
    CONF.register_opts(deploy_opts, group)
