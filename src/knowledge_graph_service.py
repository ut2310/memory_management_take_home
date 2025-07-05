import json
import os
from typing import Dict, List, Optional, Tuple, Any, Set
from datetime import datetime
from termcolor import colored

from neo4j_service import Neo4jService
from models import RelationshipType, ToolResult, ToolSummary
from token_counter import TokenCounter
from llm_service import LLMService, Message
from tool_summary_prompts import TOOL_SUMMARY_PROMPT


class KnowledgeGraphService:
    """Service for managing tool results using a knowledge graph approach"""
    
    def __init__(self, workflow_id: str, api_key: str = None):
        """
        Initialize the knowledge graph service
        
        Args:
            workflow_id: Unique identifier for the workflow
            api_key: API key for LLM service
        """
        self.workflow_id = workflow_id
        self.neo4j_service = Neo4jService()
        self.token_counter = TokenCounter()
        self.llm_service = LLMService(api_key=api_key)
        # Initialize tool counter based on existing tools in the graph
        self.tool_counter = self._get_next_tool_counter()
        
    def _get_next_tool_counter(self) -> int:
        """Get the next tool counter based on existing tools in the graph"""
        try:
            nodes = self.neo4j_service.get_all_nodes(self.workflow_id)
            max_counter = 0
            
            for node in nodes:
                if node["id"].startswith("tool_result_TR-"):
                    # Extract counter from TR-X format
                    tool_id = node["id"].replace("tool_result_", "")
                    counter = int(tool_id.split("-")[1])
                    max_counter = max(max_counter, counter)
                    
            return max_counter
        except Exception as e:
            print(colored(f"Warning: Could not determine next tool counter: {str(e)}", "yellow"))
            return 0
        
    def close(self):
        """Close Neo4j connection"""
        self.neo4j_service.close()
        
    def add_tool_result(self, knowledge_entry: Dict[str, Any]) -> str:
        """
        Add a new tool result to the knowledge graph
        
        Args:
            knowledge_entry: Tool execution entry from knowledge sequence
            
        Returns:
            str: Tool ID (e.g., "TR-1")
        """
        self.tool_counter += 1
        tool_id = f"TR-{self.tool_counter}"
        
        # Calculate token count for the result
        result_text = json.dumps(knowledge_entry, indent=2)
        token_count = self.token_counter.count_tokens(result_text)
        
        # Create tool result
        tool_result = ToolResult(
            tool_id=tool_id,
            action_type=knowledge_entry.get("action_type", "unknown"),
            action=knowledge_entry.get("action", {}),
            result=knowledge_entry.get("result", {}),
            timestamp=knowledge_entry.get("timestamp", datetime.now().isoformat()),
            token_count=token_count,
            status=knowledge_entry.get("result", {}).get("status", "unknown")
        )
        
        # Store in Neo4j
        self._store_tool_result(tool_result, result_text)
        
        print(colored(f"Added tool result {tool_id} with {token_count} tokens", "green"))
        return tool_id
        
    def _store_tool_result(self, tool_result: ToolResult, content: str):
        """Store tool result in Neo4j"""
        # Create tool result node
        metadata = f"tool_result_{tool_result.tool_id}"
        summary = f"{tool_result.action_type}: {self._extract_brief_params(tool_result.action)} - {tool_result.status.upper()}"
        
        self.neo4j_service.update_node(
            metadata=metadata,
            summary=summary,
            content=content,
            workflow_id=self.workflow_id
        )
        
    def _extract_brief_params(self, action: Dict[str, Any]) -> str:
        """Extract brief parameter description from action"""
        if isinstance(action, dict):
            if "command" in action:
                return action["command"]
            elif "file_path" in action:
                return action["file_path"]
            elif "query" in action:
                return action["query"]
            elif "code" in action:
                return f"code modification ({len(str(action['code']))} chars)"
        return str(action)[:50] + "..." if len(str(action)) > 50 else str(action)
        
    def generate_summary(self, tool_id: str) -> Optional[ToolSummary]:
        """
        Generate summary for a tool result
        
        Args:
            tool_id: Tool ID to summarize
            
        Returns:
            ToolSummary or None if failed
        """
        try:
            # Get tool result from Neo4j
            tool_node = self.neo4j_service.get_node_by_metadata(
                self.workflow_id, 
                f"tool_result_{tool_id}"
            )
            
            if not tool_node:
                print(colored(f"Tool result {tool_id} not found", "red"))
                return None
                
            # Parse tool content
            tool_content = json.loads(tool_node["content"])
            
            # Generate summary using LLM
            summary_content, salient_data = self._generate_tool_summary(tool_content)
            
            # Calculate token count
            token_count_str = summary_content
            if salient_data:
                if isinstance(salient_data, (dict, list)):
                    token_count_str += json.dumps(salient_data)
                else:
                    token_count_str += str(salient_data)
            
            # Create summary object
            summary = ToolSummary(
                tool_id=tool_id,
                summary_content=summary_content,
                salient_data=salient_data,
                token_count=self.token_counter.count_tokens(token_count_str),
                timestamp=datetime.now().isoformat()
            )
            
            # Store summary in Neo4j
            self._store_tool_summary(summary)
            
            print(colored(f"Generated summary for {tool_id}", "green"))
            return summary
            
        except Exception as e:
            print(colored(f"Error generating summary for {tool_id}: {str(e)}", "red"))
            return None
            
    def _generate_tool_summary(self, tool_content: Dict[str, Any]) -> Tuple[str, Optional[Any]]:
        """Generate summary and salient data for a tool result"""
        try:
            result = self.llm_service.generate_summary(tool_content, TOOL_SUMMARY_PROMPT)
            
            summary = result.get("summary", "")
            salient_data = result.get("salient_data")
            
            return summary, salient_data
            
        except Exception as e:
            print(colored(f"Error in LLM summary generation: {str(e)}", "red"))
            return f"Summary generation failed: {str(e)}", None
            
    def _store_tool_summary(self, summary: ToolSummary):
        """Store tool summary in Neo4j"""
        # Create summary node
        summary_metadata = f"summary_{summary.tool_id}"
        
        # Prepare content
        summary_content = {
            "summary": summary.summary_content,
            "salient_data": summary.salient_data,
            "token_count": summary.token_count,
            "timestamp": summary.timestamp
        }
        
        # Serialize the entire content to JSON for storage
        content_json = json.dumps(summary_content)
        
        self.neo4j_service.update_node(
            metadata=summary_metadata,
            summary=f"Summary of {summary.tool_id}",
            content=content_json,
            workflow_id=self.workflow_id
        )
        
        # Create relationship between tool and summary
        self.neo4j_service.update_edge(
            source_metadata=f"tool_result_{summary.tool_id}",
            target_metadata=summary_metadata,
            relation_type=RelationshipType.SUMMARIZES,
            description=f"Summary of tool result {summary.tool_id}",
            workflow_id=self.workflow_id
        )
        
    def get_all_tool_results(self) -> List[ToolResult]:
        """Get all tool results for display"""
        tool_results = []
        
        # Get all tool result nodes
        nodes = self.neo4j_service.get_all_nodes(self.workflow_id)
        
        for node in nodes:
            if node["id"].startswith("tool_result_"):
                tool_id = node["id"].replace("tool_result_", "")
                content = json.loads(node["content"])
                
                tool_result = ToolResult(
                    tool_id=tool_id,
                    action_type=content.get("action_type", "unknown"),
                    action=content.get("action", {}),
                    result=content.get("result", {}),
                    timestamp=content.get("timestamp", ""),
                    token_count=self.token_counter.count_tokens(json.dumps(content)),
                    status=content.get("result", {}).get("status", "unknown")
                )
                
                tool_results.append(tool_result)
                
        # Sort by tool ID number
        tool_results.sort(key=lambda x: int(x.tool_id.split("-")[1]))
        return tool_results
        
    def compress_tool_results(self, tool_ids: List[str]) -> bool:
        """
        Compress multiple tool results
        
        Args:
            tool_ids: List of tool IDs to compress
            
        Returns:
            bool: Success status
        """
        try:
            # Get individual summaries for all tools
            summaries = []
            
            for tool_id in tool_ids:
                # Try to get existing summary
                summary_node = self.neo4j_service.get_node_by_metadata(
                    self.workflow_id,
                    f"summary_{tool_id}"
                )
                
                if summary_node:
                    summary_content = json.loads(summary_node["content"])
                    summaries.append(f"[{tool_id}] {summary_content['summary']}")
                else:
                    # Generate summary if it doesn't exist
                    self.generate_summary(tool_id)
                    summary_node = self.neo4j_service.get_node_by_metadata(
                        self.workflow_id,
                        f"summary_{tool_id}"
                    )
                    if summary_node:
                        summary_content = json.loads(summary_node["content"])
                        summaries.append(f"[{tool_id}] {summary_content['summary']}")
                    else:
                        summaries.append(f"[{tool_id}] Summary not available")
            
            # Create compression node with individual summaries
            compression_id = f"compression_{'-'.join(tool_ids)}"
            compression_content = {
                "compressed_tools": tool_ids,
                "summary": " | ".join(summaries),
                "timestamp": datetime.now().isoformat()
            }
            
            self.neo4j_service.update_node(
                metadata=compression_id,
                summary=f"Compression of tools {', '.join(tool_ids)}",
                content=json.dumps(compression_content),
                workflow_id=self.workflow_id
            )
            
            # Create relationships to compressed tools
            for tool_id in tool_ids:
                self.neo4j_service.update_edge(
                    source_metadata=compression_id,
                    target_metadata=f"tool_result_{tool_id}",
                    relation_type=RelationshipType.COMPRESSES,
                    description=f"Compresses tool {tool_id}",
                    workflow_id=self.workflow_id
                )
                
            print(colored(f"Compressed tools {', '.join(tool_ids)}", "green"))
            return True
            
        except Exception as e:
            print(colored(f"Error compressing tools: {str(e)}", "red"))
            return False
        
    def retrieve_tool_result_with_salient_data(self, tool_id: str) -> Optional[str]:
        """
        Retrieve summary with salient data for a tool
        
        Args:
            tool_id: Tool ID to retrieve
            
        Returns:
            Formatted string with summary and salient data
        """
        try:
            # Get summary node
            summary_node = self.neo4j_service.get_node_by_metadata(
                self.workflow_id,
                f"summary_{tool_id}"
            )
            
            if not summary_node:
                return None
                
            summary_content = json.loads(summary_node["content"])
            summary_text = summary_content.get("summary", "")
            salient_data = summary_content.get("salient_data")
            
            # Format the result with salient data
            if salient_data:
                if isinstance(salient_data, dict) and salient_data:
                    salient_parts = []
                    for key, value in salient_data.items():
                        if isinstance(value, str) and len(value) > 50:
                            value = value[:50] + "..."
                        salient_parts.append(f"{key}: {value}")
                    return f"{summary_text} ({', '.join(salient_parts)})"
                    
                elif isinstance(salient_data, str) and salient_data.strip():
                    return f"{summary_text} ({salient_data})"
                        
                elif isinstance(salient_data, list) and salient_data:
                    return f"{summary_text} ({', '.join(str(item) for item in salient_data)})"
            
            return summary_text
                
        except Exception as e:
            print(colored(f"Error retrieving summary with salient data for {tool_id}: {str(e)}", "red"))
            return None
            
    def retrieve_tool_result(self, tool_id: str, summary: bool = False) -> Optional[str]:
        """
        Retrieve full tool result or summary
        
        Args:
            tool_id: Tool ID to retrieve
            summary: If True, return summary instead of full result
            
        Returns:
            Formatted tool result or None if not found
        """
        try:
            if summary:
                # Get summary
                summary_node = self.neo4j_service.get_node_by_metadata(
                    self.workflow_id,
                    f"summary_{tool_id}"
                )
                
                if summary_node:
                    summary_content = json.loads(summary_node["content"])
                    return summary_content["summary"]
                else:
                    return f"Summary not available for {tool_id}"
                    
            else:
                # Get full result
                tool_node = self.neo4j_service.get_node_by_metadata(
                    self.workflow_id,
                    f"tool_result_{tool_id}"
                )
                
                if tool_node:
                    tool_content = json.loads(tool_node["content"])
                    return self._format_full_tool_result(tool_id, tool_content)
                else:
                    return f"Tool result not found for {tool_id}"
                    
        except Exception as e:
            print(colored(f"Error retrieving tool result {tool_id}: {str(e)}", "red"))
            return f"Error retrieving {tool_id}: {str(e)}"
            
    def _format_full_tool_result(self, tool_id: str, content: Dict[str, Any]) -> str:
        """Format full tool result for display"""
        action = content.get("action", {})
        result = content.get("result", {})
        
        lines = [
            f"[{tool_id}] {content.get('action_type', 'unknown')}:",
            f"Input: {json.dumps(action, indent=2)}",
            f"Result: {result.get('status', 'unknown')}",
            f"Output: {result.get('output', 'None')}",
            f"Error: {result.get('error', 'None')}"
        ]
        
        return "\n".join(lines)
        
    def reset_workflow(self):
        """Reset all data for this workflow"""
        self.neo4j_service.reset_graph_by_workflow(self.workflow_id)
        self.tool_counter = 0
        print(colored(f"Reset workflow {self.workflow_id}", "yellow"))
        
    def generate_dashboard(self, compressed_tool_groups: Dict[str, Dict[str, Any]] = None,
                          expanded_tools: Set[str] = None) -> str:
        """
        Generate tool dashboard with compression/expansion state
        
        Args:
            compressed_tool_groups: Dict mapping group_id -> {tool_ids, summary, timestamp}
            expanded_tools: Set of tool IDs that should show expanded details
            
        Returns:
            str: Formatted tool dashboard
        """
        if compressed_tool_groups is None:
            compressed_tool_groups = {}
        if expanded_tools is None:
            expanded_tools = set()
        
        # Get all tool results
        tool_results = self.get_all_tool_results()
        
        if not tool_results:
            return "=== ACTIVE TOOL RESULTS ===\nNo tool results yet."
        
        # Build a set of all compressed tool IDs for quick lookup
        compressed_tool_ids = set()
        for group_info in compressed_tool_groups.values():
            compressed_tool_ids.update(group_info.get("tool_ids", []))
        
        # Generate dashboard
        lines = ["=== ACTIVE TOOL RESULTS ==="]
        total_tokens = 0
        
        for tool in tool_results:
            tool_id = tool.tool_id
            
            # Check if this tool is compressed
            if tool_id in compressed_tool_ids and tool_id not in expanded_tools:
                # Show compressed version
                summary_with_data = self.retrieve_tool_result_with_salient_data(tool_id)
                if summary_with_data:
                    lines.append(f"[{tool_id}] {summary_with_data} [COMPRESSED]")
                else:
                    summary = self.retrieve_tool_result(tool_id, summary=True)
                    lines.append(f"[{tool_id}] {summary} [COMPRESSED]")
            else:
                # Show full expanded view
                status = tool.status.upper()
                warning = " ⚠️" if tool.status == "error" or tool.token_count > 5000 else ""
                
                lines.append(f"[{tool_id}] {tool.action_type} - {status} ({tool.token_count:,} tokens){warning}")
                lines.append(f"Input: {json.dumps(tool.action)}")
                lines.append(f"Result: {status.lower()}")
                
                output = tool.result.get("output", "")
                if output:
                    lines.append(f"Output: {output}")
                
                error = tool.result.get("error", "")
                if error:
                    lines.append(f"Error: {error}")
            
            lines.append("")  # Add spacing between tools
            total_tokens += tool.token_count
        
        # Add token usage summary
        max_tokens = 100000
        usage_percent = (total_tokens / max_tokens) * 100
        lines.append(f"Token Usage: {total_tokens:,} / {max_tokens:,} ({usage_percent:.1f}%)")
        
        return "\n".join(lines) 