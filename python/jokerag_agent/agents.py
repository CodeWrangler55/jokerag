from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from collections.abc import Callable, Iterable, Mapping, Sequence

from .models import JokeCandidate
from .rag import Document

try:  # pragma: no cover - exercised when crewai is installed
    from crewai import Agent, Crew, Task
except Exception:  # pragma: no cover - fallback for lean test environments
    Agent = Crew = Task = None  # type: ignore[assignment]


@dataclass(frozen=True, slots=True)
class CrewRoleSpec:
    name: str
    goal: str
    backstory: str


@dataclass(frozen=True, slots=True)
class WorkflowPromptBundle:
    research: str
    comedian: str
    editor: str


def build_crewai_role_specs() -> tuple[CrewRoleSpec, CrewRoleSpec, CrewRoleSpec]:
    return (
        CrewRoleSpec(
            name="Research Agent",
            goal="Summarize the retrieved headline context for joke generation.",
            backstory="Reads the Pinecone hits, extracts the useful details, and keeps the setup grounded in real news.",
        ),
        CrewRoleSpec(
            name="Comedian Agent",
            goal="Generate ten punchy jokes from the summarized news context.",
            backstory="Turns real headlines into short candidate jokes while keeping the source facts visible.",
        ),
        CrewRoleSpec(
            name="Editor Agent",
            goal="Reject weak, repetitive, or off-tone jokes and refine the rest.",
            backstory="Applies the final editorial pass before the joke set is published.",
        ),
    )


def build_research_summary_prompt(topic: str, context: Iterable[Document], joke_count: int = 10) -> str:
    context_lines = _context_lines(context)
    lines = [
        f"Role: Research Agent",
        f"Topic: {topic}",
        f"Goal: Summarize the retrieved headlines for a set of {joke_count} jokes.",
        "Focus on what makes the headlines funny, timely, or surprising.",
        "Return a short briefing that names the relevant source headlines and the main angles to use.",
        "Retrieved headlines:",
    ]
    lines.extend(f"- {line}" for line in context_lines)
    return "\n".join(lines)


def build_comedian_prompt(
    topic: str,
    context: Iterable[Document],
    research_summary: str,
    joke_count: int = 10,
) -> str:
    context_lines = _context_lines(context)
    lines = [
        f"Role: Comedian Agent",
        f"Topic: {topic}",
        f"Research summary: {research_summary}",
        f"Goal: Write exactly {joke_count} jokes grounded in the retrieved headlines.",
        "Keep each joke short, punchy, and tied to the supplied source headlines.",
        "Use the source headlines below as the factual anchor.",
        "Source headlines:",
    ]
    lines.extend(f"- {line}" for line in context_lines)
    return "\n".join(lines)


def build_editor_prompt(
    topic: str,
    draft_jokes: Sequence[JokeCandidate],
    research_summary: str,
) -> str:
    lines = [
        f"Role: Editor Agent",
        f"Topic: {topic}",
        f"Research summary: {research_summary}",
        "Goal: Reject weak, repetitive, or off-tone jokes and refine the remainder.",
        "Keep jokes that clearly connect back to the real headlines and remove anything that reads lazy or unsafe.",
        "Draft jokes:",
    ]
    lines.extend(
        f"- {candidate.id}: {candidate.text} (sources: {', '.join(candidate.headline_ids) or 'none'})"
        for candidate in draft_jokes
    )
    return "\n".join(lines)


def build_prompt_bundle(
    topic: str,
    context: Iterable[Document],
    research_summary: str,
    joke_count: int = 10,
) -> WorkflowPromptBundle:
    materialized = list(context)
    return WorkflowPromptBundle(
        research=build_research_summary_prompt(topic, materialized, joke_count=joke_count),
        comedian=build_comedian_prompt(topic, materialized, research_summary, joke_count=joke_count),
        editor=build_editor_prompt(topic, [], research_summary),
    )


def build_crewai_plan(
    topic: str,
    context: Iterable[Document],
    joke_count: int = 10,
    research_summary: str = "",
) -> dict[str, object]:
    role_specs = build_crewai_role_specs()
    materialized = list(context)
    prompts = build_prompt_bundle(topic, materialized, research_summary, joke_count=joke_count)
    plan: dict[str, object] = {
        "topic": topic,
        "joke_count": joke_count,
        "roles": [asdict(role) for role in role_specs],
        "prompts": asdict(prompts),
        "context": [document.page_content for document in materialized],
        "context_documents": [_document_payload(document) for document in materialized],
    }
    if Agent is None or Task is None or Crew is None:
        return plan

    researcher = Agent(
        role=role_specs[0].name,
        goal=role_specs[0].goal,
        backstory=role_specs[0].backstory,
        allow_delegation=False,
        verbose=False,
    )
    comedian = Agent(
        role=role_specs[1].name,
        goal=role_specs[1].goal,
        backstory=role_specs[1].backstory,
        allow_delegation=False,
        verbose=False,
    )
    editor = Agent(
        role=role_specs[2].name,
        goal=role_specs[2].goal,
        backstory=role_specs[2].backstory,
        allow_delegation=False,
        verbose=False,
    )

    tasks = [
        Task(
            description=prompts.research,
            agent=researcher,
        ),
        Task(
            description=prompts.comedian,
            agent=comedian,
        ),
        Task(
            description=prompts.editor,
            agent=editor,
        ),
    ]
    crew = Crew(agents=[researcher, comedian, editor], tasks=tasks)
    plan["crew"] = crew
    plan["tasks"] = tasks
    return plan


def summarize_retrieved_context(
    topic: str,
    context: Iterable[Document],
    joke_count: int = 10,
) -> str:
    materialized = list(context)
    if not materialized:
        return f"No retrieved headlines were available for {topic}."

    lines = [
        f"Topic: {topic}",
        f"Target jokes: {joke_count}",
        "Key source headlines:",
    ]
    for document in materialized:
        headline_id = str(document.metadata.get("id", "unknown"))
        source = document.metadata.get("source", "unknown source")
        lines.append(f"- {headline_id}: {document.page_content} ({source})")
    lines.append("Angle: keep the jokes grounded in the real headline wording and the named source details.")
    return "\n".join(lines)


def generate_jokes_with_callback(
    topic: str,
    context: Iterable[Document],
    joke_count: int,
    generator: Callable[[str, list[str]], list[str]],
    research_summary: str = "",
) -> list[JokeCandidate]:
    materialized = list(context)
    prompt = build_comedian_prompt(topic, materialized, research_summary, joke_count=joke_count)
    joke_texts = list(generator(prompt, [doc.page_content for doc in materialized]))
    if len(joke_texts) < joke_count:
        raise ValueError(f"generator returned {len(joke_texts)} jokes, expected at least {joke_count}")
    joke_texts = joke_texts[:joke_count]
    return [
        JokeCandidate(
            id=f"joke-{index + 1}",
            text=text,
            headline_ids=_headline_ids_for_joke(materialized, index),
            votes=0,
            created_at=_now_iso(offset_minutes=index),
        )
        for index, text in enumerate(joke_texts)
    ]


def apply_editor_pass(
    topic: str,
    draft_candidates: Sequence[JokeCandidate],
    research_summary: str,
    editor: Callable[[str, list[dict[str, object]]], list[object]] | None = None,
) -> list[JokeCandidate]:
    prompt = build_editor_prompt(topic, draft_candidates, research_summary)
    if editor is None:
        return _default_editor_pass(draft_candidates)

    edited = editor(prompt, [asdict(candidate) for candidate in draft_candidates])
    return _coerce_editor_output(edited, draft_candidates)


def _default_editor_pass(draft_candidates: Sequence[JokeCandidate]) -> list[JokeCandidate]:
    accepted: list[JokeCandidate] = []
    for candidate in draft_candidates:
        text = candidate.text.strip()
        if not text:
            continue
        lowered = text.lower()
        if any(marker in lowered for marker in ("off-tone", "unsafe", "boring", "bad joke")):
            continue
        if len(text) < 8:
            continue
        accepted.append(candidate)
    return accepted or list(draft_candidates[:1])


def _coerce_editor_output(
    edited: Sequence[object],
    draft_candidates: Sequence[JokeCandidate],
) -> list[JokeCandidate]:
    fallback_by_id = {candidate.id: candidate for candidate in draft_candidates}
    fallback_by_text = {candidate.text: candidate for candidate in draft_candidates}
    coerced: list[JokeCandidate] = []

    for index, item in enumerate(edited):
        if isinstance(item, JokeCandidate):
            coerced.append(item)
            continue
        if isinstance(item, str):
            fallback = draft_candidates[index] if index < len(draft_candidates) else draft_candidates[-1]
            coerced.append(
                JokeCandidate(
                    id=fallback.id,
                    text=item,
                    headline_ids=fallback.headline_ids,
                    votes=fallback.votes,
                    created_at=fallback.created_at,
                )
            )
            continue
        if isinstance(item, Mapping):
            candidate_id = str(item.get("id", ""))
            fallback = (
                fallback_by_id.get(candidate_id)
                or fallback_by_text.get(str(item.get("text", "")))
                or (draft_candidates[index] if index < len(draft_candidates) else draft_candidates[-1])
            )
            headline_ids = item.get("headline_ids", fallback.headline_ids)
            if isinstance(headline_ids, str):
                headline_ids = (headline_ids,)
            coerced.append(
                JokeCandidate(
                    id=str(item.get("id", fallback.id)),
                    text=str(item.get("text", fallback.text)),
                    headline_ids=tuple(str(value) for value in headline_ids),
                    votes=int(item.get("votes", fallback.votes)),
                    created_at=str(item.get("created_at", fallback.created_at)),
                )
            )
            continue
        fallback = draft_candidates[index] if index < len(draft_candidates) else draft_candidates[-1]
        coerced.append(fallback)

    return coerced


def _context_lines(context: Iterable[Document]) -> list[str]:
    lines: list[str] = []
    for document in context:
        headline_id = str(document.metadata.get("id", "unknown"))
        source = document.metadata.get("source", "unknown source")
        lines.append(f"{headline_id}: {document.page_content} [{source}]")
    return lines


def _headline_ids_for_joke(context: Sequence[Document], index: int) -> tuple[str, ...]:
    if not context:
        return ()
    document = context[index % len(context)]
    headline_id = document.metadata.get("id")
    if headline_id is None:
        return ()
    return (str(headline_id),)


def _document_payload(document: Document) -> dict[str, object]:
    return {
        "page_content": document.page_content,
        "metadata": dict(document.metadata),
    }


def _now_iso(*, offset_minutes: int = 0) -> str:
    moment = datetime.now(timezone.utc)
    if offset_minutes:
        from datetime import timedelta

        moment += timedelta(minutes=offset_minutes)
    return moment.isoformat(timespec="seconds").replace("+00:00", "Z")
