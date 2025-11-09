from typing import Optional


class MongoRouter:
    """数据库路由器

    - 规则：`platform_app` 的模型走 `mongo`，其余走默认库
    - 同时限制跨库关联
    """

    app_label = "platform_app"
    mongo_alias = "mongo"

    def db_for_read(self, model, **hints) -> Optional[str]:
        if model._meta.app_label == self.app_label:
            return self.mongo_alias
        return None

    def db_for_write(self, model, **hints) -> Optional[str]:
        if model._meta.app_label == self.app_label:
            return self.mongo_alias
        return None

    def allow_relation(self, obj1, obj2, **hints) -> Optional[bool]:
        # 允许同库关联，禁止跨库关联
        if obj1._state.db and obj2._state.db:
            return obj1._state.db == obj2._state.db
        return None

    def allow_migrate(self, db: str, app_label: str, model_name: Optional[str] = None, **hints) -> Optional[bool]:
        # platform_app 仅在 mongo 上迁移，其它应用仅在 default 上迁移
        if app_label == self.app_label:
            return db == self.mongo_alias
        return db == "default"


