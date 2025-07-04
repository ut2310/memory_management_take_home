import os
from typing import Tuple
from neo4j import GraphDatabase


class Neo4jAdapter:
    """Neo4j database adapter for graph operations"""
    
    def __init__(self, uri: str = None, auth: Tuple[str, str] = None):
        if uri is None:
            uri = os.getenv("NEO4J_URI")
        if not uri:
            raise ValueError(
                "Neo4j URI missing. "
                "Pass `uri=` or set NEO4J_URI environment variable."
            )
        
        if auth is None:
            auth = (os.getenv("NEO4J_USERNAME"), os.getenv("NEO4J_PASSWORD"))
        if not auth or not auth[0] or not auth[1]:
            raise ValueError(
                "Neo4j auth missing. "
                "Pass `auth=` or set NEO4J_USERNAME and NEO4J_PASSWORD environment variables."
            )
        
        # Verify connectivity
        with GraphDatabase.driver(uri, auth=auth) as driver:
            driver.verify_connectivity()
        
        self.driver = GraphDatabase.driver(uri, auth=auth)
    
    def close(self):
        """Close the database connection"""
        self.driver.close() 