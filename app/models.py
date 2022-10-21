from tortoise import fields, models


class User(models.Model):
    id = fields.IntField(pk=True)
    name = fields.CharField(max_length=50)
    email = fields.CharField(max_length=128, unique=True, index=True, null=True)
    password_hash = fields.CharField(max_length=128, null=True)

    create_at = fields.DatetimeField()
    last_login_at = fields.DatetimeField(null=True)

    line: fields.ReverseRelation["LineLogin"]
    line_notify: fields.ReverseRelation["LineNotify"]
    line_notify_records: fields.ReverseRelation["LineNotifyRecord"]

    class Meta:
        table = "users"

    def __str__(self):
        return f"User(id={self.id}, name={self.name}"


class LineLogin(models.Model):
    update_at = fields.DatetimeField(null=True)
    access_token = fields.CharField(max_length=300)
    refresh_token = fields.CharField(max_length=300)
    expires_in = fields.DatetimeField()
    sub = fields.CharField(
        max_length=200,
        index=True,
        description="User ID for which the ID token is generated",
    )
    name = fields.CharField(max_length=50)
    picture = fields.CharField(max_length=200)
    email = fields.CharField(max_length=128, null=True)

    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", on_delete=fields.CASCADE, related_name="line", pk=True
    )

    class Meta:
        table = "line_login"

    def __str__(self):
        return f"LineLogin(sub={self.sub}, name={self.name}"


class LineNotify(models.Model):
    create_at = fields.DatetimeField()
    update_at = fields.DatetimeField(null=True)
    access_token = fields.CharField(max_length=300)
    is_revoked = fields.BooleanField(default=False)
    user: fields.OneToOneRelation[User] = fields.OneToOneField(
        "models.User", on_delete=fields.CASCADE, related_name="line_notify", pk=True
    )

    class Meta:
        table = "line_notify"

    def __str__(self):
        return (
            f"LineNotify(access_token={self.access_token}, is_revoked={self.is_revoked}"
        )


class LineNotifyRecord(models.Model):
    id = fields.IntField(pk=True)
    create_at = fields.DatetimeField(index=True)
    message = fields.TextField()
    image_thumb_nil = fields.TextField(null=True)
    image_full_size = fields.TextField(null=True)
    user: fields.ForeignKeyRelation[User] = fields.ForeignKeyField(
        "models.User", related_name="line_notify_records", on_delete=fields.CASCADE
    )

    class Meta:
        table = "line_notify_records"

    def __str__(self):
        return f"LineNotifyRecord(id={self.id}, create_at={self.create_at}"
