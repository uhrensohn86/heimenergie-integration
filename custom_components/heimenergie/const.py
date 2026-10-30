"""Constants for HeimEnergie."""
DOMAIN = "heimenergie"
PLATFORMS = ["sensor"]
CONF_DEVICES = "devices"
CONF_POWER_ENTITIES = "power_entities"
CONF_PRICE_ENTITY = "price_entity"
CONF_PRICE_FIXED = "price_fixed"
CONF_BASE_MONTHLY = "base_monthly"
PERIODS = ("today", "week", "month", "year")
PERIOD_LABELS = {"today": "Heute", "week": "Woche", "month": "Monat", "year": "Jahr"}
