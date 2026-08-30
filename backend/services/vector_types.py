import json

from sqlalchemy import Text
from sqlalchemy.types import TypeDecorator


class PortableVector(TypeDecorator):
    """JSON text on SQLite and a native pgvector column on PostgreSQL."""

    impl = Text
    cache_ok = True

    def __init__(self, dimensions: int = 384, *args, **kwargs):
        self.dimensions = dimensions
        super().__init__(*args, **kwargs)

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from pgvector.sqlalchemy import Vector
            return dialect.type_descriptor(Vector(self.dimensions))
        return dialect.type_descriptor(Text())

    def process_bind_param(self, value, dialect):
        if value is None:
            return None
        if dialect.name == "postgresql":
            if isinstance(value, str):
                value = json.loads(value)
            return [float(item) for item in value]
        return value if isinstance(value, str) else json.dumps([float(item) for item in value])
