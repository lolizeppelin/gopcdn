from simpleutil.log import log as logging
from simpleutil.config import cfg

from simpleservice.ormdb.api import MysqlDriver

from goperation import lock

from gopcdn.config import endpoint_group

CONF = cfg.CONF

DbDriver = None


LOG = logging.getLogger(__name__)

def init_endpoint_session():
    global DbDriver
    if DbDriver is None:
        with lock.get('mysql-gopcdn'):
            if DbDriver is None:
                LOG.info("Try connect database for gopcdn")
                mysql_driver = MysqlDriver(endpoint_group.name,
                                           CONF[endpoint_group.name])
                mysql_driver.start()
                DbDriver = mysql_driver
    else:
        LOG.warning("Do not call init_endpoint_session more then once")


def endpoint_session(readonly=False):
    if DbDriver is None:
        init_endpoint_session()
    return DbDriver.get_session(read=readonly,
                                autocommit=True,
                                expire_on_commit=False)