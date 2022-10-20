from tortoise import fields, models
###
from app.schemas.auth import LoginTypeEnum

class User(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)
    email = fields.CharField(max_length=128, unique=True, index=True)
    password_hash = fields.CharField(max_length=128, null=True)

    last_login = fields.DatetimeField()
    last_logout = fields.DatetimeField()

    login_type = fields.CharEnumField(LoginTypeEnum)
    session_id = fields.CharField(max_length=100, unique=True, index=True)

    line: fields.ReverseRelation["LineLogin"]
    line_notify: fields.ReverseRelation["LineNotify"]

    class Meta:
        table = "users"

    def __str__(self):
        return f"User(id={self.id}, name={self.name}"

class LineLogin(models.Model):
    access_token = fields.CharField(max_length=100)
    refresh_token = fields.CharField(max_length=100)
    expires_in = fields.DatetimeField()
    sub = fields.CharField(max_length=50)
    name = fields.CharField(max_length=50)
    picture = fields.CharField(max_length=200)
    email = fields.CharField(max_length=128, null=True)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", on_delete=fields.CASCADE, related_name="line", pk=True
    )


class LineNotify(models.Model):
    access_token = fields.CharField(max_length=100)
    is_revoked = fields.BooleanField(default=False)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", on_delete=fields.CASCADE, related_name="line_notify", pk=True
    )
    records: fields.ReverseRelation["LineNotifyRecord"]

class LineNotifyRecord(models.Model):
    id = fields.IntField(pk=True)
    create_at = fields.DatetimeField(index=True)
    message = fields.TextField()
    image_thumb_nil = fields.TextField(null=True)
    image_full_size = fields.TextField(null=True)
    line_notify: fields.ForeignKeyRelation[LineNotify] = fields.ForeignKeyField(
        "models.LineNotify", related_name="records", 
    )