from simpleutil.config import cfg

CONF = cfg.CONF


checkout_opts = [
    cfg.IntOpt('max_checkout_time',
               min=30,
               default=3600,
               help='Max checkout time'),
]
