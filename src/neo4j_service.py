import os
from typing import Dict, List
from neo4j_adapter import Neo4jAdapter
from models import RelationshipType


class Neo4jService:
    """Service for Neo4j database operations"""
    
    def __init__(self):
        uri = os.getenv("NEO4J_URI")
        auth = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
        self.adapter = Neo4jAdapter(uri, auth)

    def close(self):
        """Close the database connection"""
        self.adapter.close()

    def test_connection(self):
        """Test the database connection"""
        try:
            with self.adapter.driver.session() as session:
                result = session.run("RETURN 1 as test")
                record = result.single()
                if record and record["test"] == 1:
                    return True
                else:
                    raise Exception("Connection test failed")
        except Exception as e:
            raise Exception(f"Neo4j connection test failed: {str(e)}")

    def update_node(self, metadata: str, summary: str, content: str, workflow_id: str):
        """Create or update a node in the graph"""
        query = """
        MERGE (n:Node {id: $id})
        SET n.summary = $summary,
            n.content = $content,
            n.workflow_id = $workflow_id
        """
        with self.adapter.driver.session() as session:
            session.write_transaction(
                lambda tx: tx.run(
                    query, 
                    id=metadata, 
                    summary=summary, 
                    content=content, 
                    workflow_id=workflow_id
                )
            )

    def update_edge(
        self,
        source_metadata: str,
        target_metadata: str,
        relation_type: RelationshipType,
        description: str,
        workflow_id: str
    ):
        """Create or update an edge between two nodes"""
        sanitized_relation = relation_type.value.upper().replace(" ", "_")

        query = f"""
            MATCH (a:Node {{id: $source_metadata}})
            MATCH (b:Node {{id: $target_metadata}})
            MERGE (a)-[r:{sanitized_relation}]->(b)
            SET  r.source_metadata  = $source_metadata,
                 r.target_metadata  = $target_metadata,
                 r.relation_type    = $relation_type_str,
                 r.description      = $description,
                 r.workflow_id      = $workflow_id
        """
        with self.adapter.driver.session() as session:
            session.write_transaction(
                lambda tx: tx.run(
                    query,
                    source_metadata=source_metadata,
                    target_metadata=target_metadata,
                    relation_type_str=relation_type.value,
                    description=description,
                    workflow_id=workflow_id
                )
            )

    def delete_node(self, workflow_id: str, metadata: str, force: bool = True):
        """Delete a node by metadata ID within the given workflow"""
        with self.adapter.driver.session() as session:
            if force:
                query = """
                MATCH (n:Node {id: $id, workflow_id: $wid})
                DETACH DELETE n
                """
            else:
                query = """
                MATCH (n:Node {id: $id, workflow_id: $wid})
                WHERE NOT (n)-[]-()
                DELETE n
                """
            session.write_transaction(lambda tx: tx.run(query, id=metadata, wid=workflow_id))

    def delete_edge(self, workflow_id: str, source_metadata: str, target_metadata: str):
        """Delete an edge between two nodes"""
        query = """
        MATCH (a:Node {id: $source_id, workflow_id: $wid})
            -[r]-
            (b:Node {id: $target_id, workflow_id: $wid})
        DELETE r
        """
        with self.adapter.driver.session() as session:
            session.write_transaction(
                lambda tx: tx.run(
                    query,
                    source_id=source_metadata,
                    target_id=target_metadata,
                    wid=workflow_id
                )
            )

    def get_all_nodes(self, workflow_id: str) -> List[Dict]:
        """Get all nodes in the workflow"""
        query = "MATCH (n:Node {workflow_id: $wid}) RETURN n"
        with self.adapter.driver.session() as session:
            return session.read_transaction(
                lambda tx: [dict(record["n"]) for record in tx.run(query, wid=workflow_id)]
            )

    def get_all_edges(self, workflow_id: str) -> List[Dict]:
        """Get all edges in the workflow"""
        query = """
        MATCH (a:Node {workflow_id: $wid})-[r]->(b:Node {workflow_id: $wid})
        RETURN a, r, b
        """
        with self.adapter.driver.session() as session:
            return session.read_transaction(
                lambda tx: [
                    {
                        "source": record["a"]["id"],
                        "target": record["b"]["id"],
                        "relation_type": record["r"].get("relation_type"),
                        "description": record["r"].get("description")
                    }
                    for record in tx.run(query, wid=workflow_id)
                ]
            )

    def get_node_by_metadata(self, workflow_id: str, metadata: str) -> Dict:
        """Get a node by its metadata ID"""
        query = "MATCH (n:Node {id: $node_id, workflow_id: $wid}) RETURN n"
        with self.adapter.driver.session() as session:
            def fetch_one(tx):
                result = tx.run(query, node_id=metadata, wid=workflow_id)
                rec = result.single()
                return dict(rec["n"]) if rec else None
            return session.read_transaction(fetch_one)

    def reset_graph_by_workflow(self, workflow_id: str) -> None:
        """Delete all nodes and relationships for a workflow"""
        query = """
        MATCH (n:Node {workflow_id: $wid})
        DETACH DELETE n
        """
        with self.adapter.driver.session() as session:
            session.write_transaction(lambda tx: tx.run(query, wid=workflow_id))

    def reset_entire_graph(self) -> None:
        """Delete all nodes and relationships in the entire database"""
        query = "MATCH (n) DETACH DELETE n"
        with self.adapter.driver.session() as session:
            session.write_transaction(lambda tx: tx.run(query))

    # Additional methods for tool result operations
    def store_tool_result(self, tool_id: str, tool_result) -> Dict:
        """Store a tool result in the database"""
        query = """
        MERGE (t:ToolResult {id: $tool_id})
        SET t.status = $status,
            t.output = $output,
            t.action_type = $action_type,
            t.action = $action,
            t.result = $result,
            t.timestamp = $timestamp,
            t.token_count = $token_count
        RETURN t
        """
        with self.adapter.driver.session() as session:
            result = session.write_transaction(
                lambda tx: tx.run(
                    query,
                    tool_id=tool_id,
                    status=tool_result.status,
                    output=str(tool_result.result.get("output", "")),
                    action_type=tool_result.action_type,
                    action=str(tool_result.action),
                    result=str(tool_result.result),
                    timestamp=tool_result.timestamp,
                    token_count=tool_result.token_count
                )
            )
            return {"tool_id": tool_id, "status": "stored"}

    def get_tool_result(self, tool_id: str) -> Dict:
        """Get a tool result by ID"""
        query = "MATCH (t:ToolResult {id: $tool_id}) RETURN t"
        with self.adapter.driver.session() as session:
            def fetch_tool(tx):
                result = tx.run(query, tool_id=tool_id)
                record = result.single()
                return dict(record["t"]) if record else None
            
            return session.read_transaction(fetch_tool)

    def store_compressed_result(self, compressed_result) -> Dict:
        """Store a compressed tool result"""
        query = """
        MERGE (c:CompressedResult {id: $tool_id})
        SET c.summary = $summary,
            c.salient_data = $salient_data,
            c.original_token_count = $original_token_count,
            c.compressed_token_count = $compressed_token_count
        RETURN c
        """
        with self.adapter.driver.session() as session:
            result = session.write_transaction(
                lambda tx: tx.run(
                    query,
                    tool_id=compressed_result.tool_id,
                    summary=compressed_result.summary,
                    salient_data=str(compressed_result.salient_data) if compressed_result.salient_data else None,
                    original_token_count=compressed_result.original_token_count,
                    compressed_token_count=compressed_result.compressed_token_count
                )
            )
            return {"tool_id": compressed_result.tool_id, "status": "stored"}

    def get_compressed_result(self, tool_id: str) -> Dict:
        """Get a compressed tool result by ID"""
        query = "MATCH (c:CompressedResult {id: $tool_id}) RETURN c"
        with self.adapter.driver.session() as session:
            def fetch_compressed(tx):
                result = tx.run(query, tool_id=tool_id)
                record = result.single()
                return dict(record["c"]) if record else None
            
            return session.read_transaction(fetch_compressed)

    def create_relationship(self, source_id: str, target_id: str, relationship_type: str, description: str) -> Dict:
        """Create a relationship between two tool results"""
        query = """
        MATCH (a:ToolResult {id: $source_id})
        MATCH (b:ToolResult {id: $target_id})
        MERGE (a)-[r:RELATES_TO]->(b)
        SET r.type = $relationship_type,
            r.description = $description
        RETURN r
        """
        with self.adapter.driver.session() as session:
            result = session.write_transaction(
                lambda tx: tx.run(
                    query,
                    source_id=source_id,
                    target_id=target_id,
                    relationship_type=relationship_type,
                    description=description
                )
            )
            return {"relationship": "created"}

    def get_related_tools(self, tool_id: str) -> List[Dict]:
        """Get tools related to the given tool ID"""
        query = """
        MATCH (t:ToolResult {id: $tool_id})-[r]->(related:ToolResult)
        RETURN related, r
        """
        with self.adapter.driver.session() as session:
            def fetch_related(tx):
                result = tx.run(query, tool_id=tool_id)
                return [{"tool": dict(record["related"]), "relationship": dict(record["r"])} for record in result]
            
            return session.read_transaction(fetch_related)

    def delete_tool_result(self, tool_id: str) -> Dict:
        """Delete a tool result and its compressed version"""
        query = """
        MATCH (t:ToolResult {id: $tool_id})
        DETACH DELETE t
        """
        query2 = """
        MATCH (c:CompressedResult {id: $tool_id})
        DETACH DELETE c
        """
        with self.adapter.driver.session() as session:
            session.write_transaction(lambda tx: tx.run(query, tool_id=tool_id))
            session.write_transaction(lambda tx: tx.run(query2, tool_id=tool_id))
            return {"tool_id": tool_id, "status": "deleted"} 