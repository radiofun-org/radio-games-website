class MainRouter:
    def db_for_read(self, model, **hints):
        return "contacts" if model._meta.app_label == "contacts" else "default"

    def db_for_write(self, model, **hints):
        return None if model._meta.app_label == "contacts" else "default"

    def allow_relation(self, obj1, obj2, **hints):
        return obj1._state.db == obj2._state.db

    def allow_migrate(self, db, app_label, model_name=None, **hints):
        return app_label != "contacts"
