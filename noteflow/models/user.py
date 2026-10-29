from aurora.aurorasql import Model, column


class User(Model):
    """Store account details and a password hash."""

    __table__ = "users"

    id = column(int, primary_key=True)
    username = column(str, length=100, unique=True)
    email = column(str, length=254, unique=True)
    password_hash = column(str, length=255)
