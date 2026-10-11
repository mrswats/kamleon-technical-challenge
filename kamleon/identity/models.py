import uuid
from datetime import datetime

from sqlalchemy import DateTime
from sqlalchemy import String
from sqlalchemy import Uuid
from sqlalchemy.orm import Mapped
from sqlalchemy.orm import mapped_column

from kamleon.db import Base
from kamleon.db import TimestampMixin


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(150))
    email: Mapped[str] = mapped_column(String(320), unique=True)
    # Set when the customer is "deleted". The row is kept (devices and measurements still
    # reference it) but its personal data is anonymised. See `service.delete_customer`.
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
