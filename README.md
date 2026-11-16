## Autonoma-
Autonoma is a virtual AI company that takes a client's project from brief to final delivery no human team required. AI agents handle planning, design, coding (via Claude/Codex), and testing, with human approval at key milestones. One dashboard tracks the entire journey: order received, work in progress, client feedback, final delivery.
# Problem statement
Building a product requires a full team -> a business analyst, product manager, architect, engineers, testers, and DevOps. Most early-stage founders and small startups can't afford to hire that team, and even if they could, they don't have the time to recruit, manage, and coordinate one. This forces founders to either delay building their product, compromise on quality by doing everything themselves, or burn through limited funding on hires before they've even validated their idea.
## Solution
Autonoma is a virtual AI company that turns a single client brief into a shipped product with no human team required. A client describes what they want, and a chain of AI agents (Business Analyst, Product Manager, Architect, Engineer, QA, DevOps) takes it from requirements to a deployed, working product  each agent powered by a real LLM (Claude, Codex, GPT) acting as an "employee" in their role. Human approval gates sit at key milestones, so the client stays in control without needing to manage a team. Built for founders and startups who can't afford or don't have time to hire a full team, Autonoma replaces the cost of hiring with the cost of AI  giving anyone the ability to run product development like a company of one.

## Run it on your computer

The agents run on a local model through [Ollama](https://ollama.com). No API key and no internet connection are needed once the model is downloaded.

**You need**

- Node.js 22.12 or newer (the current LTS from nodejs.org)
- Python 3.9 or newer
- Ollama, with one model downloaded:
  - 8 GB of memory: `ollama pull qwen2.5-coder:7b` (about 4.7 GB)
  - 16 GB of memory or more: `ollama pull qwen2.5-coder:14b` (about 9 GB, better results)

**Set up (once)**

```
npm install
python3 -m pip install -r requirements.txt
npm run doctor
```

On Windows use `python` instead of `python3`. `npm run doctor` checks Node, Python, Ollama and the model, and prints the exact command for anything that is missing. Run it again until it says everything is in place.

**Start**

```
npm run dev
```

The header shows "Engine Ready" and the model name when the agents can work.

**What to expect from a local model**

A laptop model is much slower and weaker than a large cloud model. Long steps take minutes, a whole project takes many hours, and the Judge may send work back more often. Keep the first project small (for example a to-do list app), and close browsers and other heavy apps while the agents work.
