# Memory Management Take-Home Assignment

## Assignment

**Understand the current memory management system, improve it, and prove your improvement works better.**

The current system manages memory for an AI agent that executes DevOps tools. Your job is to:

1. **Understand** how the current memory management works
2. **Improve** the memory management approach 
3. **Test** that your approach is better than the current one

## What You're Working With

### Agent Execution Data

- `examples/agent_knowledge_sequence.txt` - Real agent execution showing how tools are compressed/expanded in practice and how they're displayed in the prompt of our agent
- `examples/tool_execution_trace.json` - Raw tool execution data that needs to be managed

### Current System

The agent executes tools like:
- `execute_command` (AWS CLI, terraform, etc.)
- `create_file`, `modify_code`, `read_file_contents`  
- `query_codebase`
- Integration method calls

Each tool execution generates results that consume tokens. The system uses:
- **Neo4j graph database** for storing tool results and relationships
- **LLM summarization** (GPT-4o-mini) for compressing tool results
- **Token counting** (tiktoken) for memory tracking
- **Compression/expansion** for managing what's visible vs. stored

Current performance on example data:
- Original: 2,694 tokens
- Basic compression: 101 tokens (96.3% reduction)

## Codebase Structure

```
src/
├── knowledge_graph_service.py  # Main memory management logic
├── neo4j_service.py           # Database operations  
├── neo4j_adapter.py           # Database connection
├── llm_service.py             # LLM integration for summarization
├── tool_summary_prompts.py    # Prompts for summarization
├── token_counter.py           # Token counting utility
└── models.py                  # Data structures
```

### Key Components

**KnowledgeGraphService** - Main class that:
- Stores tool results in Neo4j with full context
- Generates LLM summaries with salient data extraction  
- Compresses multiple tool results into summary groups
- Retrieves full details or summaries as needed
- Tracks relationships between tools

**Current Limitations:**
- Simple compression (just concatenates summaries)
- No semantic understanding of tool relationships
- Static summarization approach for all tool types
- No learning from usage patterns

## Setup

```bash
pip install -r requirements.txt
```

**Environment variables needed for full functionality:**
```
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j  
NEO4J_PASSWORD=your-password
OPENAI_API_KEY=sk-your-key
```

**Test basic functionality:**
```bash
python -c "
from src.token_counter import TokenCounter
tc = TokenCounter()
print(f'Token counter works: {tc.count_tokens(\"test\")} tokens')
"
```

## Expected Deliverable

Working code that demonstrates a better memory management approach with evidence that it's superior to the current system.
