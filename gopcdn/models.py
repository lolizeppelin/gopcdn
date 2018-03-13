import sqlalchemy as sa
from sqlalchemy import orm
from sqlalchemy.ext import declarative

from sqlalchemy.dialects.mysql import VARCHAR
from sqlalchemy.dialects.mysql import SMALLINT
from sqlalchemy.dialects.mysql import INTEGER
from sqlalchemy.dialects.mysql import BIGINT
from sqlalchemy.dialects.mysql import BLOB
from sqlalchemy.dialects.mysql import BOOLEAN

from simpleutil.utils import uuidutils

from simpleservice.ormdb.models import TableBase
from simpleservice.ormdb.models import InnoDBTableBase
from simpleservice.ormdb.models import MyISAMTableBase

from gopcdn import common


TableBase = declarative.declarative_base(cls=TableBase)


class CdnResourceRemark(TableBase):
    remark_id = sa.Column(INTEGER(unsigned=True), nullable=False, primary_key=True, autoincrement=True)
    resource_id = sa.Column(sa.ForeignKey('cdnresources.resource_id',
                                          ondelete="CASCADE", onupdate='RESTRICT'),
                            nullable=False)
    rtime = sa.Column(INTEGER(unsigned=True), nullable=False)
    username = sa.Column(VARCHAR(64), nullable=False)
    message = sa.Column(VARCHAR(512), nullable=False)


class ResourceQuote(TableBase):
    quote_id = sa.Column(INTEGER(unsigned=True), nullable=False, primary_key=True, autoincrement=True)
    version_id = sa.Column(sa.ForeignKey('resourceversions.version_id', ondelete="CASCADE", onupdate='RESTRICT'),
                           nullable=False)
    desc = sa.Column(VARCHAR(256), nullable=True)
    __table_args__ = (
        sa.Index('resource_index', version_id),
        InnoDBTableBase.__table_args__
    )


class ResourceVersion(TableBase):
    version_id = sa.Column(INTEGER(unsigned=True), nullable=False, primary_key=True, autoincrement=True)
    resource_id = sa.Column(sa.ForeignKey('cdnresources.resource_id', ondelete="RESTRICT", onupdate='RESTRICT'),
                            nullable=False, primary_key=True)
    version = sa.Column(VARCHAR(64), nullable=False)
    alias = sa.Column(VARCHAR(64), nullable=True)
    vtime = sa.Column(INTEGER(unsigned=True), nullable=False)
    desc = sa.Column(VARCHAR(256), nullable=True)
    quotes = orm.relationship(ResourceQuote, backref='cdnresourceversion', lazy='select',
                              cascade='delete,delete-orphan,save-update')
    __table_args__ = (
        sa.Index('resource_index', resource_id),
        sa.UniqueConstraint('resource_id', 'version', name='unique_version'),
        InnoDBTableBase.__table_args__
    )


class CdnResource(TableBase):
    resource_id = sa.Column(INTEGER(unsigned=True), nullable=False, primary_key=True, autoincrement=True)
    entity = sa.Column(sa.ForeignKey('cdndomains.entity', ondelete="RESTRICT", onupdate='RESTRICT'),
                       nullable=False)
    name = sa.Column(VARCHAR(64), nullable=False)
    etype = sa.Column(VARCHAR(64), nullable=False)
    status = sa.Column(SMALLINT, nullable=False, default=common.ENABLE)
    impl = sa.Column(VARCHAR(32), nullable=False, default='svn')
    auth = sa.Column(BLOB, nullable=True)
    quotes = sa.Column(INTEGER(unsigned=True), nullable=False, default=0)
    versions = orm.relationship(ResourceVersion, backref='cdnresource', lazy='select',
                                cascade='delete,delete-orphan,save-update')
    desc = sa.Column(VARCHAR(1024), nullable=True)
    __table_args__ = (
            sa.UniqueConstraint('entity', 'name', 'etype', name='unique_etype'),
            sa.Index('impl_index', 'impl'),
            InnoDBTableBase.__table_args__
    )


class Domain(TableBase):
    domain = sa.Column(VARCHAR(200), nullable=False, primary_key=True)
    entity = sa.Column(sa.ForeignKey('cdndomains.entity', ondelete="CASCADE", onupdate='RESTRICT'),
                       nullable=False)


class CdnDomain(TableBase):
    entity = sa.Column(INTEGER(unsigned=True), nullable=False, primary_key=True, autoincrement=True)
    internal = sa.Column(BOOLEAN, default=False)
    agent_id = sa.Column(INTEGER(unsigned=True), nullable=False)
    port = sa.Column(SMALLINT(unsigned=True), nullable=False)
    character_set = sa.Column(VARCHAR(64), default=None)
    domains = orm.relationship(Domain, backref='cdndomain', lazy='select',
                               cascade='delete,delete-orphan,save-update')
    resources = orm.relationship(CdnResource, backref='cdndomain', lazy='select',
                                 cascade='delete,delete-orphan,save-update')
    __table_args__ = (
        InnoDBTableBase.__table_args__
    )


class CheckOutLog(TableBase):
    log_time = sa.Column(BIGINT(unsigned=True), nullable=False, default=uuidutils.Gkey, primary_key=True)
    resource_id = sa.Column(INTEGER(unsigned=True), nullable=False)
    version = sa.Column(VARCHAR(64), nullable=False)
    start = sa.Column(INTEGER(unsigned=True), nullable=False)
    end = sa.Column(INTEGER(unsigned=True), nullable=False)
    size_change = sa.Column(BIGINT(unsigned=True), nullable=False)
    logfile = sa.Column(VARCHAR(512), nullable=True)
    result = sa.Column(VARCHAR(1024), nullable=False, default='unkonwn result')
    detail = sa.Column(BLOB, nullable=True)
    __table_args__ = (
        sa.Index('resource_id', 'version'),
        MyISAMTableBase.__table_args__
    )
