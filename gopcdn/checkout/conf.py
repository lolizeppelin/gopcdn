from simpleutil.config import cfg

CONF = cfg.CONF


checkout_opts = [
    cfg.IntOpt('checkout_timeout',
               min=30,
               default=3600,
               help='Max checkout time'),
]
