from django.apps import AppConfig


class PluginConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "plugin"
    dpy_package = "plugin.package"
