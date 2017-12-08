import datetime

import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext import declarative

from sqlalchemy.dialects.mysql import VARCHAR
from sqlalchemy.dialects.mysql import CHAR
from sqlalchemy.dialects.mysql import SMALLINT
from sqlalchemy.dialects.mysql import TINYINT
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.dialects.mysql import BLOB


from simpleutil.utils import uuidutils

from simpleservice.ormdb.models import TableBase
from simpleservice.ormdb.models import InnoDBTableBase
from simpleservice.ormdb.models import MyISAMTableBase

from gopcdn import common


TableBase = declarative.declarative_base(cls=TableBase)


class PackageSource(TableBase):
    package_id = sa.Column(sa.ForeignKey('packages.package_id', ondelete="CASCADE", onupdate='RESTRICT'),
                           nullable=False, primary_key=True)
    ptype = sa.Column(sa.SMALLINT, nullable=False, primary_key=True)
    address = sa.Column(VARCHAR(128), nullable=False)
    desc = sa.Column(VARCHAR(256), nullable=True)
    __table_args__ = (
            sa.UniqueConstraint('address', name='address_unique'),
            InnoDBTableBase.__table_args__
    )


class Package(TableBase):
    package_id = sa.Column(INTEGER(unsigned=True), nullable=False,
                           primary_key=True, autoincrement=True)
    entity = sa.Column(sa.ForeignKey('checkoutresources.entity', ondelete="CASCADE", onupdate='RESTRICT'),
                       nullable=False)
    endpoint = sa.Column(VARCHAR(64), default=None)
    name = sa.Column(VARCHAR(256), nullable=False)
    group = sa.Column(INTEGER(unsigned=True), nullable=True, default=None)
    version = sa.Column(VARCHAR(64), nullable=False, default='1.0')
    mark = sa.Column(VARCHAR(16), nullable=False)
    status = sa.Column(sa.SMALLINT, nullable=False, default=common.ENABLE)
    uptime = sa.Column(sa.DATETIME, nullable=False, onupdate=datetime.datetime.now)
    magic = sa.Column(BLOB, nullable=True)
    desc = sa.Column(VARCHAR(256), nullable=True)
    sources = orm.relationship(PackageSource, backref='package', lazy='select',
                               cascade='delete,delete-orphan,save-update')
    __table_args__ = (
            sa.Index('endpoint_index', 'endpoint'),
            InnoDBTableBase.__table_args__
    )


class CheckOutResource(TableBase):
    entity = sa.Column(INTEGER(unsigned=True), nullable=False, primary_key=True)
    agent_id = sa.Column(INTEGER(unsigned=True), nullable=False,
                         default=1, primary_key=True)
    etype = sa.Column(SMALLINT(unsigned=True), nullable=False)
    endpoint = sa.Column(VARCHAR(64), default=None)
    name = sa.Column(VARCHAR(256), nullable=False)
    version = sa.Column(VARCHAR(64), default=None)
    status = sa.Column(SMALLINT, nullable=False, default=common.DISENABLE)
    impl = sa.Column(VARCHAR(32), nullable=False, default='svn')
    uri = sa.Column(VARCHAR(512), nullable=False)
    cdnhost = sa.Column(BLOB, nullable=True)
    auth = sa.Column(BLOB, nullable=True)
    packages = orm.relationship(Package, backref='checkoutresource', lazy='select',
                                cascade='delete,delete-orphan,save-update')
    desc = sa.Column(VARCHAR(1024), nullable=True)
    __table_args__ = (
            sa.Index('impl_index', 'impl'),
            InnoDBTableBase.__table_args__
    )


CdnResource = CheckOutResource


class CheckOutLog(TableBase):
    log_time = sa.Column(BIGINT(unsigned=True), nullable=False, default=uuidutils.Gkey, primary_key=True)
    entity = sa.Column(INTEGER(unsigned=True), nullable=False)
    start = sa.Column(INTEGER(unsigned=True), nullable=False)
    end = sa.Column(INTEGER(unsigned=True), nullable=False)
    size_change = sa.Column(BIGINT(unsigned=True), nullable=False)
    logfile = sa.Column(VARCHAR(512), nullable=True)
    result = sa.Column(VARCHAR(1024), nullable=False, default='unkonwn result')
    detail = sa.Column(BLOB, nullable=True)
    __table_args__ = (
            MyISAMTableBase.__table_args__
    )