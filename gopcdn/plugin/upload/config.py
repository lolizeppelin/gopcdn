from simpleutil.config import cfg

CONF = cfg.CONF

upload_opts = [
    cfg.IntOpt('upload_timeout',
               min=30,
               default=3600,
               help='Max checkout time'),
]


def register_opts(group):
    # upload config for gopcdn
    CONF.register_opts(upload_opts, group)
