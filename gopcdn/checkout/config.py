from simpleutil.config import cfg

CONF = cfg.CONF


checkout_opts = [
    cfg.IntOpt('checkout_timeout',
               min=30,
               default=3600,
               help='Max checkout time'),
]


def register_opts(group):
    # checkout config for gopcdn
    CONF.register_opts(checkout_opts, group)
