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
# v0.2.3: consumer assignment and deliberate session separation.
CONF_EDIT_CONSUMERS = "edit_consumers"
CONF_CONSUMER_DEVICE = "consumer_device"
CONF_CONSUMER_NAME = "consumer_name"
CONF_CONSUMER_TYPE = "consumer_type"
CONF_NEW_SESSION = "new_session"
