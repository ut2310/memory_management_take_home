# Memory Management Take-Home Assignment

## Motivation

As AI applications have moved from single-turn inference to multi-turn agents, new challenges have emerged that must be addressed to keep agents running for long periods while maintaining high efficacy.

One major challenge is memory. As agents interact with their environment, they receive feedback that must be retained in context. However, this feedback is often context-heavy and/or accumulates over many turns, making it infeasible to store full action histories and results within input context limits.

To solve this, we need memory so the agent can recall past actions and results, helping it continue toward the goal with minimal performance loss. 

## Goal

In an ideal situation, the agent would remember everything it did in pursuit of a goal in its full representation. A good memory system gets us as close to this ideal as possible while still operating within input context constraints. 

Your goal is to understand how the DevOps agent works, understand the current memory-management approach, and improve it.

## What You're Working With

### Agent Overview

The agent's action space consists of these tools and these are the only outputs the agent is capable of:

**Codebase Tools:**
```xml
<codebase_tools>
  <tool>
    name: "modify_code"
    params: {files: [string], instructions: string, code: string}
    description: "Call this whenever you need to modify code files. Files should be a list of FULL file paths that need to be modified, instructions should be clear about what changes to make, and code should be a snippet of what should be adjusted."
  </tool>
  <tool>
    name: "execute_command"
    params: {command: string, background: boolean}
    description: "Call this whenever you need to execute a shell command. Background should be true for long-running commands."
  </tool>
  <tool>
    name: "query_codebase"
    params: {query: string}
    description: "Call this for when you need chunks of relevant code from across the codebase. Query the codebase for relevant information."
  </tool>
  <tool>
    name: "run_file"
    params: {file_path: string, args: list[string], cwd: string}
    description: "Call this whenever you need to execute a specific file. File path should be the full correct path to the file, args should be a list of arguments to pass to the file, and cwd should be the current working directory."
  </tool>
  <tool>
    name: "delete_file"
    params: {file_path: string, cwd: string}
    description: "Call this whenever you need to delete a file. File path should be the full correct path to the file, and cwd should be the current working directory."
  </tool>
  <tool>
    name: "create_file"
    params: {file_path: string, content: string, mode: int, cwd: string}
    description: "Call this whenever you need to create a new file or replace the entire contents of an existing file. File path should be the full correct path to the file, content should be the content of the file, mode should be the mode of the file, and cwd should be the current working directory."
  </tool>
  <tool>
    name: "read_file_contents"
    params: {file_path: string, cwd: string}
    description: "Call this whenever you need to read the contents of a file. File path should be the full correct path to the file, and cwd should be the current working directory."
  </tool>
</codebase_tools>
```

**Documentation Tools:**
```xml
<documentation_tools>
  <tool>
    name: "search_documentation"
    params: {query: string, language: string, provider_version: string, search_method: string}
    description: "Call this whenever you need to search documentation for a specific IaC language. Query should be the query to search for, language should be the IaC language to search for, provider_version should be the provider version to search for, and search_method should be the method to search for."
  </tool>
  <tool>
    name: "search_internet"
    params: {query: string}
    description: "Call this whenever you need to search the internet for general documentation. Query should be the query to search for."
  </tool>
</documentation_tools>
```

**Integration Tools:**
```xml
<integration_tools>
  <!-- These are tools you can call to interact with DevOps integrations the user has configured.
       You will start by calling retrieve_integration_methods to get the tools you need, 
       then you can call those directly -->
  <tool>
    name: "retrieve_integration_methods"
    params: {query: string, integrations: list[string]}
    description: "Call this when you need to get integration tools to interact with one of the following integrations the user has configured: {configured_integrations}. The query parameter is a description of what methods you're looking for, and the integrations parameter is a list of the integrations you need to get methods for, and this parameter should never be left to be an empty list."
  </tool>
</integration_tools>
```

**Memory Management Tools:**
```xml
<memory_management_tools>
  <tool>
    name: "compress_tool_results"
    params: {tool_ids: list[string]}
    description: "Compress one or more tool results to save context space. Replaces full tool results with individual summaries for each tool. Use when token usage is getting high; monitor token usage in dashboard."
  </tool>
  <tool>
    name: "get_tool_result"
    params: {tool_id: string}
    description: "Retrieve full details of a previously executed tool result (inputs/outputs) given its ID (e.g., TR-1)."
  </tool>
</memory_management_tools>
```

**Workflow Control:**
```xml
<workflow_control>
  <tool>
    name: "workflow_complete"
    params: {}
    description: "Call this when you need to mark the entire workflow as complete. This should be the last tool you call."
  </tool>
</workflow_control>
```


This agent we're building memory management for takes these inputs:

**1. Plan Steps**

```python
class PlanStep(BaseModel):
    """
    Represents a single step in an execution plan.

    Each step describes a specific action to be taken during plan execution.
    Now aligned with YAML workflow structure for direct mapping.

    Attributes:
        name (str): Name of the step
        type (str): Type of step (prompt, cli, or integration name)
        prompt (str, optional): AI prompt for prompt steps
        command (str, optional): Command for CLI steps
        method (str, optional): Full method name including integration for integration steps (e.g., 'aws.iam.ListUsers')
        parameters (Dict, optional): Parameters for the step
        files (List[str]): List of files involved in this step (empty until frontend support)
    """

    name: str
    prompt: str = ""
    files: List[str] = Field(default_factory=list)

class Plan(BaseModel):
    """
    Represents a complete execution plan with multiple steps.

    A plan contains an ordered sequence of steps to accomplish a goal,

    Attributes:
        goal (str): Overall goal of the workflow
        steps (List[PlanStep]): Ordered list of plan steps
    """

    goal: str
    steps: List[PlanStep]
```

**2. Tool Dashboard**

A formatted history of all past tool calls and results. As an example:

```
=== ACTIVE TOOL RESULTS ===
[TR-1] retrieve_integration_methods - SUCCESS (1,363 tokens)
Input: {"kwargs": {"query": "AWS integration methods", "integrations": ["aws"]}}
Result: success
Output: Retrieved integration methods:

AWS METHODS:
<tool>{{name: "aws.connect.ListContactFlowVersions", params: {{Region: string (optional), InstanceId: string (required), ContactFlowId: string (required), NextToken: string (optional), MaxResults: integer (optional)}}, description: "Lists all the versions for the specified flow.. Docstring: Returns all the available versions for the specified Amazon Connect instance and flow identifier.    See also: `AWS API Documentation <https://docs.aws.amazon.com/goto/WebAPI/connect-2017-08-08/ListContactFlowVersions>`_   **Request Syntax** ::    response = client.list_contact_flow_versions(       InstanceId='string',       ContactFlowId='string',       NextToken='string',       MaxResults=123   )    :type InstanceId: string :param InstanceId: **[REQUIRED]**     The identifier of the Amazon Connect instance.       :type ContactFlowId: string :param ContactFlowId: **[REQUIRED]**     The identifier of the flow.       :type NextToken: string :param NextToken:     The token for the next set of results. Use the value returned in the previous response in the next request to retrieve the next se…"}}</tool>

[TR-2] Successfully retrieved AWS integration methods for STS and IAM, providing a list of available API methods and their parameters. (methods: [{'name': 'aws.connect.ListContactFlowVersions', 'description': 'Lists the different versions of a specified contact flow.', 'params': {'Region': 'string (optional)', 'InstanceId': 'string (required)', 'ContactFlowId': 'string (required)', 'NextToken': 'string (optional)', 'MaxResults': 'integer (optional)'}, 'documentation': 'https://docs.aws.amazon.com/goto/WebAPI/connect-2017-08-08/ListContactFlowVersions'}, {'name': 'aws.connect.ListViewVersions', 'description': 'Lists the different versions of a specified view.', 'params': {'Region': 'string (optional)', 'InstanceId': 'string (required)', 'ViewId': 'string (required)', 'NextToken': 'string (optional)', 'MaxResults': 'integer (optional)'}, 'documentation': 'https://docs.aws.amazon.com/goto/WebAPI/connect-2017-08-08/ListViewVersions'}, {'name': 'aws.lookoutequipment.ListDatasets', 'description': 'Lists all datasets for which you have access to data.', 'params': {'Region': 'string (optional)', 'NextToken': 'string (optional)', 'MaxResults': 'integer (optional)', 'DatasetNameBeginsWith': 'string (optional)'}, 'documentation': 'https://docs.aws.amazon.com/goto/WebAPI/lookoutequipment-2020-12-15/ListDatasets'}, {'name': 'aws.lookoutequipment.ListInferenceSchedulers', 'description': 'Lists all inference schedulers for a given dataset.', 'params': {'Region': 'string (optional)', 'NextToken': 'string (optional)', 'MaxResults': 'integer (optional)', 'InferenceSchedulerNameBeginsWith': 'string (optional)', 'ModelName': 'string (optional)', 'Status': 'string (optional)'}}, {'name': 'aws.bcm-data-exports.ListTables', 'description': 'Lists all tables in a dataset.', 'params': {'Region': 'string (optional)', 'MaxResults': 'integer (optional)', 'NextToken': 'string (optional)'}}, {'name': 'aws.inspector.ListRulesPackages', 'description': 'Lists the IP address ranges that are associated with the specified rules package.', 'params': {'Region': 'string (optional)', 'nextToken': 'string (optional)', 'maxResults': 'integer (optional)'}}, {'name': 'aws.databrew.ListRulesets', 'description': 'Lists the rulesets available in the current account and Amazon Web Services Region.', 'params': {'Region': 'string (optional)', 'TargetArn': 'string (optional)', 'MaxResults': 'integer (optional)', 'NextToken': 'string (optional)'}}, {'name': 'aws.controltower.ListBaselines', 'description': 'Lists the baselines for an account and Amazon Web Services Region.', 'params': {'Region': 'string (optional)', 'maxResults': 'integer (optional)', 'nextToken': 'string (optional)'}}, {'name': 'aws.glue.ListCrawlers', 'description': 'Lists all crawlers defined in the account.', 'params': {'Region': 'string (optional)', 'MaxResults': 'integer (optional)', 'NextToken': 'string (optional)', 'Tags': 'map (optional)'}}, {'name': 'aws.glue.ListJobs', 'description': 'Lists jobs for the current account.', 'params': {'Region': 'string (optional)', 'NextToken': 'string (optional)', 'MaxResults': 'integer (optional)', 'Tags': 'map (optional)'}}]) [COMPRESSED]

[TR-3] execute_command - SUCCESS (183 tokens)
Input: {"command": "aws sts get-caller-identity"}
Result: success
Output: 
{
    "UserId": "AIDA6IY35VFGU4ESXCB6M",
    "Account": "980921723213",
    "Arn": "arn:aws:iam::980921723213:user/sritan-iam"
}
```

**3. Configured Integrations List**

Per project, the user can configure integrations (e.g., AWS, GCP, Grafana, Splunk). The agent can call prebuilt tools specific to these integrations, so it's notified of what's available. Example list:

```json
["AWS", "GCP", "Splunk"]
```

**4. Integration Methods**

This field starts out empty and only gets populated when the agent runs its method-retrieval tool. This tool allows the agent to query a large set of tools with natural language and get the tools it needs to take an action within an integration. Example:

```xml
<tool>
  name: "aws.connect.ListContactFlowVersions"
  params: {Region: string (optional), InstanceId: string (required), ContactFlowId: string (required), NextToken: string (optional), MaxResults: integer (optional)}
  description: "Lists all the versions for the specified flow. Returns all the available versions for the specified Amazon Connect instance and flow identifier."
  documentation: "https://docs.aws.amazon.com/goto/WebAPI/connect-2017-08-08/ListContactFlowVersions"
</tool>
```

**5. Detected IaC Languages**

A dict of detected Infrastructure as Code (IaC) languages present in the codebase with their versions. The languages specifically include **Terraform**, **Terraform CDK**, **Ansible**, **Pulumi**, and **AWS CDK**. The detected languages and versions are indexed by folder. Example:

```json
{
    "example_folder": {
        "terraform_cdk": "v6.5.0"
    },
    "example_folder_2": {
        "ansible": "v4.22.32",
        "terraform": "v3.5.0"
    }
}
```


### Codebase Breakdown

The system uses:

- **Neo4j graph database** for storing tool results and relationships
- **LLM summarization** for compressing tool results  
- **Token counting** (tiktoken) for memory tracking
- **Compression/expansion** for managing what's visible vs. stored

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

#### Key Components

**`KnowledgeGraphService`** - Main class that:

- Stores tool results in Neo4j with full context
- Generates LLM summaries with salient data extraction  
- Compresses multiple tool results into summary groups
- Retrieves full details or summaries as needed
- Tracks relationships between tools

#### Setup

```bash
python -m venv venv

source venv/bin/activate

pip install -r requirements.txt
```

**Environment variables needed for full functionality:**

```bash
NEO4J_URI=neo4j+s://your-instance.databases.neo4j.io
NEO4J_USERNAME=neo4j  
NEO4J_PASSWORD=your-password
OPENAI_API_KEY=sk-your-key
```

Use your own Neo4j credentials; an OpenAI API key will be provided.

#### Agent Execution Data

- **`examples/agent_knowledge_sequence.txt`** - Real agent execution showing how tools are compressed/expanded in practice and how they're displayed in the prompt of our agent
- **`examples/tool_execution_trace.json`** - Raw tool execution data that needs to be managed  
- **`src/sample_agent_prompt.py`** - Actual prompt that the agent uses

#### Live Demo

**`demo_compression.py`** - A demonstration of how the agent's memory management can work in practice:

The agent continuously summarizes tool results as they are executed, in parallel with planning the next action, to maximize efficiency.

It demonstrates how:
- Related tool executions (e.g., AWS operations, file modifications) are grouped and compressed when memory pressure increases
- The agent selectively expands compressed tools back to full detail when that information becomes relevant  
- The workflow progresses from: **raw tool results** → **summaries** → **compression** → **selective expansion** based on what the agent needs

Run with:

```bash
python demo_compression.py
```

This gives you a concrete example of how an agent would manage its memory throughout a complex **DevOps workflow**, maintaining efficiency while preserving access to detailed information when needed.

---

## Expected Deliverable

### Caveats

You don't have access to running the actual agent, so you will need to operate with limited testing ability.

- Using **synthetically generated data** can be very helpful.

### Final Deliverable

You need to expand upon, or design, a **new memory system** that will exceed the performance of the current system. The goal you are optimizing for is a system that **minimizes repeated tool calls caused by forgetting**. 

If the agent makes a tool call it already made previously purely because it didn't have enough information about its context—and not for another reason (e.g., the tool call previously failed, or the environment changed since the last run and now the call has different expected outputs)—then the agent's memory management has room for improvement.

There is a lot of room for exploration within this task, so feel free to take your own route and use the ideas presented above to the extent you see fit. 

---

## Logistics

You have the alloted time provided in the email to finish the task. During this time, feel free to send batches of questions to **rithvik@a37.ai**.

After the allotted time period, we'll schedule a call where you'll walk us through your:
- **Exploration process**
- **Code implementation**  
- **Final results**