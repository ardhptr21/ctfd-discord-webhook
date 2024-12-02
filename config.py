from os import environ


def config(app):
    app.config["DISCORD_WEBHOOK_URL"] = environ.get("DISCORD_WEBHOOK_URL")
    app.config["DISCORD_WEBHOOK_LIMIT"] = environ.get("DISCORD_WEBHOOK_LIMIT", 3)
