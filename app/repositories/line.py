from typing import Iterable, Tuple, Optional, Any

###
from app import models
from app.repositories import CRUDBase


class LineLoginRepository(CRUDBase):
    def __init__(self) -> None:
        super().__init__(model=models.LineLogin)

    async def filter_with_prefetch(
        self, prefetch: Tuple[str, ...] = ("user",), **filter: Any
    ) -> Optional[models.LineLogin]:
        return (
            await models.LineLogin.filter(**filter).prefetch_related(*prefetch).first()
        )


class LineNotifyRepository(CRUDBase):
    def __init__(self) -> None:
        super().__init__(model=models.LineNotify)


class LineNotifyRecordRepository(CRUDBase):
    def __init__(self) -> None:
        super().__init__(model=models.LineNotifyRecord)

    async def get_all_with_prefetch(
        self,
        prefetch: Tuple[str, ...] = ("user",),
        order_by: str = "-create_at",
    ) -> Iterable[models.LineNotifyRecord]:
        return (
            await models.LineNotifyRecord.all()
            .prefetch_related(*prefetch)
            .order_by(order_by)
        )
