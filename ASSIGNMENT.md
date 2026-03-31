This assignment implements a local, noUI multiagent system using LangGraph as the lowlevel agent orchestration runtime and the deepagents library as an “agent harness” to accelerate development. The system supports: 

PDF Q&A: Analyze any uploaded PDF and answer user questions with grounded citations. 

Sandboxed command execution: Run userrequested shell commands safely in an isolated environment (using Modal Sandboxes)—e.g., read an Excel file and convert it to CSV. 

Skills: Package specialized capabilities as composable “skills” that agents can load and invoke on demand. 

References 

LangGraph provides durable, stateful agent execution, humanintheloop, and streaming—ideal for reliable multiagent control flow. [docs.langchain.com], [github.com] 

deepagents layers planning, filesystem, subagents, and sandbox backends on top of LangGraph so you can assemble a capable, extensible agent quickly. [docs.langchain.com], [github.com] 

Skills are a pattern for promptdriven specializations that can be loaded dynamically by an agent, keeping the core agent small and flexible. [docs.langchain.com] 

Modal Sandboxes give an API to create isolated containers and exec arbitrary commands with timeouts, streaming stdout/stderr, and optional snapshots—perfect for secure task execution. [modal.com] 