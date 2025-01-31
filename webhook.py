from flask import request
from flask.wrappers import Response
from CTFd.utils.dates import ctftime
from CTFd.models import Challenges, Solves
from CTFd.utils import config as ctfd_config
from CTFd.utils.user import get_current_team, get_current_user
from discord_webhook import DiscordWebhook, DiscordEmbed
from functools import wraps
from .config import config

import re
from urllib.parse import quote

ordinal = lambda n: "%d%s" % (
    n,
    "tsnrhtdd"[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10 :: 4],
)
sanreg = re.compile(
    r'(~|!|@|#|\$|%|\^|&|\*|\(|\)|\_|\+|\`|-|=|\[|\]|;|\'|,|\.|\/|\{|\}|\||:|"|<|>|\?)'
)
sanitize = lambda m: sanreg.sub(r"\1", m)

topConfig = {
    1: {
        "color": 0xff0000,
        "title": "**[ :first_place: FIRST BLOOD :drop_of_blood: ]**",
        "img_url": "https://i.ibb.co.com/rR9s18Hj/Banner-First-Blood.png"
    },
    2: {
        "color": 0xc3baad,
        "title": "**[ :second_place: SECOND BLOOD :drop_of_blood: ]**",
        "img_url": "https://i.ibb.co.com/XfLZyZdJ/Banner-Second-Blood.png"
    },
    3: {
        "color": 0xffaf3b,
        "title": "**[ :third_place: THIRD BLOOD :drop_of_blood: ]**",
        "img_url": "https://i.ibb.co.com/9Qq1Ybx/Banner-Third-Blood.png"
    },
}
defaultmessage = (
    "Congratulations to team {team} for the {fsolves} solve on challenge {challenge}!"
)


def load(app):
    config(app)
    TEAMS_MODE = ctfd_config.is_teams_mode()

    if not app.config["DISCORD_WEBHOOK_URL"]:
        print("No DISCORD_WEBHOOK_URL set! Plugin disabled.")
        return

    def challenge_attempt_decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            result = f(*args, **kwargs)
            if not ctftime():
                return result
            if isinstance(result, Response):
                data = result.json
                if (
                    isinstance(data, dict)
                    and data.get("success") == True
                    and isinstance(data.get("data"), dict)
                    and data.get("data").get("status") == "correct"
                ):
                    if request.content_type != "application/json":
                        request_data = request.form
                    else:
                        request_data = request.get_json()
                    challenge_id = request_data.get("challenge_id")
                    challenge = Challenges.query.filter_by(
                        id=challenge_id
                    ).first_or_404()
                    solvers = Solves.query.filter_by(challenge_id=challenge.id)
                    if TEAMS_MODE:
                        solvers = solvers.filter(Solves.team.has(hidden=False))
                    else:
                        solvers = solvers.filter(Solves.user.has(hidden=False))
                    num_solves = solvers.count()

                    limit = int(app.config["DISCORD_WEBHOOK_LIMIT"])
                    if int(limit) > 0 and num_solves > int(limit):
                        return result
                    webhook = DiscordWebhook(url=app.config["DISCORD_WEBHOOK_URL"])

                    user = get_current_user()
                    team = get_current_team()

                    format_args = {
                        "team": sanitize("" if team is None else team.name),
                        "user_id": user.id,
                        "team_id": 0 if team is None else team.id,
                        "user": sanitize(user.name),
                        "challenge": sanitize(challenge.name),
                        "challenge_slug": quote(challenge.name),
                        "value": challenge.value,
                        "solves": num_solves,
                        "fsolves": ordinal(num_solves),
                        "category": sanitize(challenge.category),
                    }

                    embed = DiscordEmbed()
                    if num_solves > 3:
                        message = defaultmessage.format(**format_args)
                        embed.set_description(message)
                    else:
                        embed.add_embed_field(":game_die: Challenge", format_args["challenge"], inline=False)
                        embed.add_embed_field(":flags: Team", format_args["team"], inline=False)
                        embed.add_embed_field(":ninja: By", format_args["user"], inline=False)
                        conf = topConfig.get(num_solves, {})
                        embed.set_color(conf.get("color", 0x00ff00))
                        embed.set_title(conf.get("title", ""))
                        embed.set_image(url=conf.get("img_url", ""))
                    webhook.add_embed(embed)
                    webhook.execute()
            return result

        return wrapper

    app.view_functions["api.challenges_challenge_attempt"] = (
        challenge_attempt_decorator(
            app.view_functions["api.challenges_challenge_attempt"]
        )
    )
