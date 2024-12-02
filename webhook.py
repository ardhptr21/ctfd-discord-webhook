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
from types import SimpleNamespace

ordinal = lambda n: "%d%s" % (
    n,
    "tsnrhtdd"[(n // 10 % 10 != 1) * (n % 10 < 4) * n % 10 :: 4],
)
sanreg = re.compile(
    r'(~|!|@|#|\$|%|\^|&|\*|\(|\)|\_|\+|\`|-|=|\[|\]|;|\'|,|\.|\/|\{|\}|\||:|"|<|>|\?)'
)
sanitize = lambda m: sanreg.sub(r"\1", m)

topmessage = {
    1: ":first_place: **First Blood!**:drop_of_blood: The battlefield just got claimed by **{user}** from team **{team}!** :rocket: They struck fast, solving the challenge **{challenge}** before anyone else could blink. Absolute legends in the making! :star2:",
    2: ":second_place: **Wowza!** Big brains {user} from team **{team}** claimed the second solve **{challenge}** like pros! :fire: Staying cool :cold_face:",
    3: ":third_place: **Respect!** **{user}** from team **{team}** snatched third solve **{challenge}** with grit and determination! :muscle: Never say die—what a brilliant! :clap: Keep the fire alive! :fire:",
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

                    limit = app.config["DISCORD_WEBHOOK_LIMIT"]
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

                    message = topmessage.get(num_solves, defaultmessage).format(
                        **format_args
                    )
                    embed = DiscordEmbed(description=message)
                    webhook.add_embed(embed)
                    webhook.execute()
            return result

        return wrapper

    app.view_functions["api.challenges_challenge_attempt"] = (
        challenge_attempt_decorator(
            app.view_functions["api.challenges_challenge_attempt"]
        )
    )
