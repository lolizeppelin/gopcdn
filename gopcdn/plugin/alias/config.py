from simpleutil.config import cfg

CONF = cfg.CONF

alias_opts = [
    cfg.MultiImportStrOpt('aliases',
                          default=[],
                          help='alias impl class'),
]


def register_opts(group):
    # checkout config for gopcdn
    CONF.register_opts(alias_opts, group)
