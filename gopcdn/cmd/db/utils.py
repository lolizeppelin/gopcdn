from simpleservice.ormdb.tools.utils import init_database

from gopcdn.models import TableBase


def init_gopcdn(db_info):
    init_database(db_info, TableBase.metadata)