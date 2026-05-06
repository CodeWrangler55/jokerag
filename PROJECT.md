# AI Joke of the Day Project Guidelines

Only specify items here that override or extend the Deft defaults.
See `deft/main.md` and the TypeScript/web standards for base rules.

**Tech Type**: Web App
**Specification**: [SPECIFICATION.md](./SPECIFICATION.md)
**Process**: Light

## Overrides

- ! Use TypeScript for all source code.
- ! The product MUST use RAG, LangChain, CrewAI, and Zapier as first-class parts of the design.
- ! The product MUST use Pinecone as the vector database for retrieval.
- ! Keep the first release focused on one end-to-end loop: news ingestion, retrieval, joke generation, voting, winner selection, and Zapier email dispatch.
- ! Treat the daily winner selection as deterministic and testable.

## Secrets

```bash
cp .env.example .env
```

Required environment variables:

- `NEWS_API_KEY`
- `OPENAI_API_KEY`
- `RESEND_API_KEY`
- `DATABASE_URL`

## Principles

- ! Prefer a simple, shippable MVP over a large agent orchestration surface.
- ! Use LangChain for retrieval and prompt chaining rather than ad hoc orchestration.
- ! Use CrewAI for role-based joke generation and refinement.
- ! Use Zapier for the daily delivery and automation boundary.
- ! Keep Pinecone on the free Starter plan by using one index, one namespace, `us-east-1`, and compact headline records.
- ! Keep headline ingestion, context retrieval, joke generation, voting, and email delivery separated by module.
- ! Make every daily outcome reproducible from stored inputs.
- ! Human votes decide the joke of the day.
- ! Store secrets outside the repository.
- Do not couple the dashboard to the generation pipeline.

## Tech Stack

**Language**: TypeScript 5 for the shell plus Python 3.11+ for the AI workflow layer
**Retrieval**: RAG with a Pinecone vector store and LangChain retrieval chains
**Vector DB**: Pinecone Starter plan, serverless, `us-east-1`
**Agent Framework**: CrewAI for research/comedian/editor role separation
**Automation**: Zapier webhooks and scheduled delivery
**Framework**: Planned Next.js dashboard and API surface
**Database**: SQLite for the MVP
**Deployment**: Web/cloud deployment with a daily scheduled worker

## Documentation

- **README**: [README.md](./README.md)
- **Specification**: [SPECIFICATION.md](./SPECIFICATION.md)

## Constraints

- **Timeline**: MVP-first, then incremental expansion
- **Compatibility**: Desktop and mobile web browsers
