from __future__ import annotations

from dataclasses import asdict

from .models import Headline, JokeCandidate


def build_zapier_webhook_payload(
    topic: str,
    winner: JokeCandidate,
    headlines: list[Headline],
    mailing_list: str,
) -> dict[str, object]:
    return {
        "topic": topic,
        "mailing_list": mailing_list,
        "winner": {
            "id": winner.id,
            "text": winner.text,
            "votes": winner.votes,
            "headline_ids": list(winner.headline_ids),
        },
        "headlines": [asdict(headline) for headline in headlines],
    }


def build_zapier_email_payload(
    topic: str,
    winner: JokeCandidate,
    headlines: list[Headline],
    mailing_list: str,
) -> dict[str, object]:
    return {
        "subject": f"Joke of the Day: {topic}",
        "body": winner.text,
        "recipient_list": mailing_list,
        "headline_count": len(headlines),
    }

