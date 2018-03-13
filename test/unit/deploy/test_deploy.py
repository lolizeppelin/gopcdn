from gopcdn import common
from simpleutil.config import cfg

CONF = cfg.CONF

CONF(project='test',  default_config_files=[])

endpoint_group = cfg.OptGroup(common.CDN)

CONF.register_group(endpoint_group)

from gopcdn.plugin.deploy import deployer

deployer = deployer('nginx')

root = 'C:\\Users\\loliz_000\\Desktop\\nginx\\gopcdn.conf'

deployer.root = root

deployer.init_conf()

deployer.deploy(urlpath='/test', rootpath='/data/test',
                configfile='C:\\Users\\loliz_000\\Desktop\\nginx\\1.conf')
