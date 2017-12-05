from simpleutil.config import cfg

CONF = cfg.CONF


deploy_opts = [
    cfg.StrOpt('deployer',
               default='nginx',
               help='Deploy impl, nginx only now'),
    cfg.StrOpt('nginx_conf',
               default='/etc/ningx/config.d/gopcdn.conf',
               help='Deploy config output path, '
                    'need add this path in to nginx.conf include'),
    cfg.HostnameOpt('cdnhost',
                    default='gopcdn.com',
                    help='Default cdn host name'),
    cfg.PortOpt('cdnport',
                default=80,
                help='Default cdn port'),
    cfg.StrOpt('charset',
               default='utf8',
               help='Default cdn charset'),
    cfg.BoolOpt('autoindex',
                default=True,
                help='Enable autoindex'),
]


def register_opts(group):
    # checkout config for gopcdn
    CONF.register_opts(deploy_opts, group)


def list_opts():
    return deploy_opts
