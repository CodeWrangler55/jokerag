from __future__ import annotations

from dataclasses import asdict, dataclass
from collections.abc import Callable, Iterable

from .models import Headline, JokeCandidate
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


def build_crewai_role_specs() -> tuple[CrewRoleSpec, CrewRoleSpec, CrewRoleSpec]:
    return (
        CrewRoleSpec(
            name="Research Agent",
            goal="Summarize relevant headline context for joke generation.",
            backstory="Reads the retrieval context and distills the parts the comedians should use.",
        ),
        CrewRoleSpec(
            name="Comedian Agent",
            goal="Generate short, punchy jokes from the retrieved news context.",
            backstory="Produces multiple joke candidates with strong headlines and clean setups.",
        ),
        CrewRoleSpec(
            name="Editor Agent",
            goal="Remove weak, repetitive, or unsafe jokes and keep the best candidates.",
            backstory="Applies a final editorial pass before the voting dashboard sees the jokes.",
        ),
    )


def build_crewai_plan(topic: str, context: Iterable[Document], joke_count: int = 10) -> dict[str, object]:
    role_specs = build_crewai_role_specs()
    if Agent is None or Task is None or Crew is None:
        return {
            "topic": topic,
            "joke_count": joke_count,
            "roles": [asdict(role) for role in role_specs],
            "context": [doc.page_content for doc in context],
        }

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
            description=f"Summarize the retrieved context for topic: {topic}",
            agent=researcher,
        ),
        Task(
            description=f"Generate {joke_count} jokes from the summarized context.",
            agent=comedian,
        ),
        Task(
            description="Edit the jokes for clarity, brevity, and punchiness.",
            agent=editor,
        ),
    ]
    crew = Crew(agents=[researcher, comedian, editor], tasks=tasks)
    return {"topic": topic, "crew": crew, "tasks": tasks}


def generate_jokes_with_callback(
    topic: str,
    context: Iterable[Document],
    joke_count: int,
    generator: Callable[[str, list[str]], list[str]],
) -> list[JokeCandidate]:
    prompt = "\n".join([f"Topic: {topic}", *[doc.page_content for doc in context]])
    joke_texts = generator(prompt, [doc.page_content for doc in context])[:joke_count]
    return [
        JokeCandidate(
            id=f"joke-{index + 1}",
            text=text,
            headline_ids=tuple(str(doc.metadata.get("id", index + 1)) for doc in context),
            votes=0,
            created_at=f"2026-04-07T00:{index:02d}:00.000Z",
        )
        for index, text in enumerate(joke_texts)
    ]
