from django.apps import AppConfig


class RentalsConfig(AppConfig):
    name = 'rentals'

    def ready(self):
        import rentals.signals  # noqa: F401
