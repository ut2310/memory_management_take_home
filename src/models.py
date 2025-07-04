from typing import Dict, List, Optional, Any
from pydantic import BaseModel
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class RelationshipType(str, Enum):
    """Allowed relationship types between nodes."""
    DEPENDS_ON = "depends_on"
    EXTENDS = "extends"
    INTEGRATES_WITH = "integrates_with"
    REPLACES = "replaces"
    COMPLEMENTS = "complements"
    GENERATES_CONFIG_FOR = "generates_config_for"
    TRIGGERS = "triggers"
    IS_TRIGGERED_BY = "is_triggered_by"
    MONITORS = "monitors"
    DEPLOYED_BY = "deployed_by"
    STORES_ARTIFACTS_IN = "stores_artifacts_in"
    AUTHENTICATES_VIA = "authenticates_via"
    MANAGES_INFRA_FOR = "manages_infra_for"
    VISUALIZES = "visualizes"
    SUMMARIZES = "summarizes"
    COMPRESSES = "compresses"


@dataclass
class ToolResult:
    """Represents a tool execution result"""
    tool_id: str
    action_type: str
    action: Dict[str, Any]
    result: Dict[str, Any]
    timestamp: str
    token_count: int
    status: str
    is_compressed: bool = False
    compressed_summary: Optional[str] = None


@dataclass
class ToolExecution:
    """Represents a complete tool execution"""
    tool_id: str
    action_type: str
    action_input: Dict[str, Any]
    result: 'ToolResult'
    timestamp: datetime


@dataclass
class CompressedToolResult:
    """Represents a compressed tool execution result"""
    tool_id: str
    summary: str
    salient_data: Optional[Dict[str, Any]]
    original_token_count: int
    compressed_token_count: int


@dataclass
class ToolSummary:
    """Represents a summary of a tool result"""
    tool_id: str
    summary_content: str
    salient_data: Optional[Any]
    token_count: int
    timestamp: str


class KnowledgeGraph(BaseModel):
    """Knowledge graph structure"""
    nodes: List[str]
    edges: Dict[str, tuple]  # source_metadata: (target_metadata, relationship, description)

    def get_neighbors(self, metadata: str, depth: int = 1) -> List[str]:
        """Get all metadata keys within specified depth from given node"""
        if depth <= 0:
            return []

        neighbors = set()
        current_level = {metadata}

        for _ in range(depth):
            next_level = set()
            for source_meta, (target_meta, relationship, description) in self.edges.items():
                for curr_node in current_level:
                    if source_meta == curr_node:
                        next_level.add(target_meta)
            neighbors.update(next_level)
            current_level = next_level

        return list(neighbors) 