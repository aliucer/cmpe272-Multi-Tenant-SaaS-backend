from sqlalchemy import (
    Column,
    Text,
    DateTime,
    func,
    ForeignKey,
    UniqueConstraint,
    Index,
    text as sa_text,
)
from sqlalchemy.dialects.postgresql import UUID
from .db import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    name = Column(Text, nullable=False, unique=True)
    stripe_customer_id = Column(Text, unique=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class User(Base):
    __tablename__ = "users"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    tenant_id = Column(UUID(as_uuid=True), ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(Text, nullable=False)
    password_hash = Column(Text, nullable=False)
    role = Column(Text, nullable=False, server_default=sa_text("'user'"))
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("tenant_id", "email", name="uq_users_tenant_email"),
    )


class Note(Base):
    __tablename__ = "notes"

    id = Column(UUID(as_uuid=True), primary_key=True, server_default=sa_text("gen_random_uuid()"))
    # Default uses current_setting('app.current_tenant', true)::uuid (see schema.sql)
    tenant_id = Column(
        UUID(as_uuid=True),
        nullable=False,
        server_default=sa_text("(current_setting('app.current_tenant', true))::uuid"),
        index=True,
    )
    title = Column(Text, nullable=False)
    body = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
    )
