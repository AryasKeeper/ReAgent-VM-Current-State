"""
ReAgent Sydney - PostgreSQL Checkpoint System

Production-ready checkpointing system using PostgreSQL for state persistence.
Ensures workflow state is maintained across restarts and failures.
"""

import json
import asyncio
from typing import Dict, Any, Optional, List, Tuple
from datetime import datetime
from uuid import uuid4

import asyncpg
from langgraph.checkpoint.base import BaseCheckpointSaver, Checkpoint, CheckpointMetadata
from langchain_core.runnables import RunnableConfig

from ..core.database.engine import get_db_session
from ..utils.logging import get_logger
from .state import ReAgentState, WorkflowStatus


logger = get_logger(__name__)


class PostgreSQLCheckpointer(BaseCheckpointSaver):
    """
    PostgreSQL-based checkpoint saver for LangGraph workflows.
    
    Provides persistent state storage with:
    - Atomic state updates
    - Concurrent access support
    - State history tracking
    - Efficient querying and cleanup
    - Production monitoring integration
    """
    
    def __init__(
        self,
        connection_string: str,
        table_name: str = "reagent_checkpoints",
        metadata_table: str = "reagent_checkpoint_metadata"
    ):
        super().__init__()
        self.connection_string = connection_string
        self.table_name = table_name
        self.metadata_table = metadata_table
        self._connection_pool: Optional[asyncpg.Pool] = None
        self._initialized = False

    async def initialize(self) -> None:
        """Initialize the checkpoint system and create tables if needed."""
        if self._initialized:
            return
            
        try:
            # Create connection pool
            self._connection_pool = await asyncpg.create_pool(
                self.connection_string,
                min_size=2,
                max_size=20,
                command_timeout=60
            )
            
            # Create tables
            await self._create_tables()
            
            self._initialized = True
            logger.info("PostgreSQL checkpoint system initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize PostgreSQL checkpoint system: {e}")
            raise

    async def _create_tables(self) -> None:
        """Create checkpoint and metadata tables."""
        async with self._connection_pool.acquire() as conn:
            # Main checkpoints table
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.table_name} (
                    thread_id VARCHAR(255) NOT NULL,
                    checkpoint_ns VARCHAR(100) NOT NULL DEFAULT '',
                    checkpoint_id VARCHAR(255) NOT NULL,
                    parent_id VARCHAR(255),
                    type VARCHAR(50),
                    checkpoint JSONB NOT NULL,
                    metadata JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    
                    PRIMARY KEY (thread_id, checkpoint_ns, checkpoint_id)
                );
            """)
            
            # Metadata table for extended information
            await conn.execute(f"""
                CREATE TABLE IF NOT EXISTS {self.metadata_table} (
                    thread_id VARCHAR(255) NOT NULL,
                    checkpoint_id VARCHAR(255) NOT NULL,
                    workflow_name VARCHAR(255),
                    workflow_status VARCHAR(50),
                    agent_results JSONB,
                    execution_metrics JSONB,
                    error_log JSONB,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    
                    PRIMARY KEY (thread_id, checkpoint_id),
                    FOREIGN KEY (thread_id, checkpoint_id) 
                        REFERENCES {self.table_name}(thread_id, checkpoint_id)
                );
            """)
            
            # Create indexes for performance
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_thread_created 
                ON {self.table_name}(thread_id, created_at DESC);
            """)
            
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.table_name}_type_created 
                ON {self.table_name}(type, created_at DESC);
            """)
            
            await conn.execute(f"""
                CREATE INDEX IF NOT EXISTS idx_{self.metadata_table}_status 
                ON {self.metadata_table}(workflow_status, created_at DESC);
            """)

    async def aget(self, config: RunnableConfig) -> Optional[Checkpoint]:
        """Retrieve the latest checkpoint for a thread."""
        if not self._initialized:
            await self.initialize()
            
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        
        try:
            async with self._connection_pool.acquire() as conn:
                result = await conn.fetchrow(f"""
                    SELECT checkpoint_id, parent_id, type, checkpoint, metadata, created_at
                    FROM {self.table_name}
                    WHERE thread_id = $1 AND checkpoint_ns = $2
                    ORDER BY created_at DESC
                    LIMIT 1;
                """, thread_id, checkpoint_ns)
                
                if not result:
                    return None
                    
                return Checkpoint(
                    v=1,
                    id=result["checkpoint_id"],
                    ts=result["created_at"].isoformat(),
                    channel_values=result["checkpoint"],
                    channel_versions={},
                    versions_seen={}
                )
                
        except Exception as e:
            logger.error(f"Failed to retrieve checkpoint for thread {thread_id}: {e}")
            raise

    async def aput(
        self,
        config: RunnableConfig,
        checkpoint: Checkpoint,
        metadata: CheckpointMetadata,
        new_versions: dict
    ) -> RunnableConfig:
        """Save a checkpoint to PostgreSQL."""
        if not self._initialized:
            await self.initialize()
            
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        checkpoint_id = checkpoint["id"]
        
        try:
            async with self._connection_pool.acquire() as conn:
                async with conn.transaction():
                    # Insert/Update main checkpoint
                    await conn.execute(f"""
                        INSERT INTO {self.table_name} 
                        (thread_id, checkpoint_ns, checkpoint_id, parent_id, type, checkpoint, metadata, updated_at)
                        VALUES ($1, $2, $3, $4, $5, $6, $7, NOW())
                        ON CONFLICT (thread_id, checkpoint_ns, checkpoint_id)
                        DO UPDATE SET
                            checkpoint = EXCLUDED.checkpoint,
                            metadata = EXCLUDED.metadata,
                            updated_at = NOW();
                    """, 
                    thread_id,
                    checkpoint_ns,
                    checkpoint_id,
                    metadata.get("parent_id"),
                    metadata.get("step", "unknown"),
                    json.dumps(checkpoint["channel_values"]),
                    json.dumps(metadata)
                    )
                    
                    # Update extended metadata if this is a ReAgent workflow
                    if isinstance(checkpoint["channel_values"], dict) and "workflow_name" in checkpoint["channel_values"]:
                        await self._save_extended_metadata(
                            conn, thread_id, checkpoint_id, checkpoint["channel_values"]
                        )
            
            logger.debug(f"Saved checkpoint {checkpoint_id} for thread {thread_id}")
            
            return {
                "configurable": {
                    **config["configurable"],
                    "checkpoint_id": checkpoint_id
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to save checkpoint {checkpoint_id} for thread {thread_id}: {e}")
            raise

    async def _save_extended_metadata(
        self,
        conn: asyncpg.Connection,
        thread_id: str,
        checkpoint_id: str,
        state_data: Dict[str, Any]
    ) -> None:
        """Save extended metadata for ReAgent workflows."""
        try:
            await conn.execute(f"""
                INSERT INTO {self.metadata_table}
                (thread_id, checkpoint_id, workflow_name, workflow_status, agent_results, execution_metrics, error_log)
                VALUES ($1, $2, $3, $4, $5, $6, $7)
                ON CONFLICT (thread_id, checkpoint_id)
                DO UPDATE SET
                    workflow_name = EXCLUDED.workflow_name,
                    workflow_status = EXCLUDED.workflow_status,
                    agent_results = EXCLUDED.agent_results,
                    execution_metrics = EXCLUDED.execution_metrics,
                    error_log = EXCLUDED.error_log;
            """,
            thread_id,
            checkpoint_id,
            state_data.get("workflow_name"),
            state_data.get("status"),
            json.dumps(state_data.get("agent_results", {})),
            json.dumps(state_data.get("metrics", {})),
            json.dumps(state_data.get("errors", []))
            )
            
        except Exception as e:
            logger.warning(f"Failed to save extended metadata: {e}")

    async def alist(
        self,
        config: RunnableConfig,
        *,
        filter: Optional[Dict[str, Any]] = None,
        before: Optional[RunnableConfig] = None,
        limit: Optional[int] = 10
    ) -> List[Checkpoint]:
        """List checkpoints for a thread with optional filtering."""
        if not self._initialized:
            await self.initialize()
            
        thread_id = config["configurable"]["thread_id"]
        checkpoint_ns = config["configurable"].get("checkpoint_ns", "")
        
        try:
            query = f"""
                SELECT checkpoint_id, parent_id, type, checkpoint, metadata, created_at
                FROM {self.table_name}
                WHERE thread_id = $1 AND checkpoint_ns = $2
            """
            params = [thread_id, checkpoint_ns]
            
            # Add before filter
            if before:
                query += " AND created_at < (SELECT created_at FROM {self.table_name} WHERE checkpoint_id = $3)"
                params.append(before["configurable"]["checkpoint_id"])
            
            # Add ordering and limit
            query += " ORDER BY created_at DESC"
            if limit:
                query += f" LIMIT ${len(params) + 1}"
                params.append(limit)
            
            async with self._connection_pool.acquire() as conn:
                results = await conn.fetch(query, *params)
                
                checkpoints = []
                for result in results:
                    checkpoints.append(Checkpoint(
                        v=1,
                        id=result["checkpoint_id"],
                        ts=result["created_at"].isoformat(),
                        channel_values=result["checkpoint"],
                        channel_versions={},
                        versions_seen={}
                    ))
                
                return checkpoints
                
        except Exception as e:
            logger.error(f"Failed to list checkpoints for thread {thread_id}: {e}")
            raise

    async def get_workflow_status(self, thread_id: str) -> Optional[Dict[str, Any]]:
        """Get workflow status and metadata."""
        if not self._initialized:
            await self.initialize()
            
        try:
            async with self._connection_pool.acquire() as conn:
                result = await conn.fetchrow(f"""
                    SELECT 
                        c.checkpoint_id,
                        c.created_at,
                        c.updated_at,
                        m.workflow_name,
                        m.workflow_status,
                        m.agent_results,
                        m.execution_metrics,
                        m.error_log
                    FROM {self.table_name} c
                    LEFT JOIN {self.metadata_table} m ON c.thread_id = m.thread_id AND c.checkpoint_id = m.checkpoint_id
                    WHERE c.thread_id = $1
                    ORDER BY c.created_at DESC
                    LIMIT 1;
                """, thread_id)
                
                if not result:
                    return None
                
                return {
                    "thread_id": thread_id,
                    "checkpoint_id": result["checkpoint_id"],
                    "workflow_name": result["workflow_name"],
                    "status": result["workflow_status"],
                    "agent_results": json.loads(result["agent_results"] or "{}"),
                    "metrics": json.loads(result["execution_metrics"] or "{}"),
                    "errors": json.loads(result["error_log"] or "[]"),
                    "created_at": result["created_at"],
                    "updated_at": result["updated_at"]
                }
                
        except Exception as e:
            logger.error(f"Failed to get workflow status for thread {thread_id}: {e}")
            raise

    async def cleanup_old_checkpoints(self, older_than_days: int = 30) -> int:
        """Clean up old checkpoints to prevent unbounded growth."""
        if not self._initialized:
            await self.initialize()
            
        try:
            async with self._connection_pool.acquire() as conn:
                async with conn.transaction():
                    # Delete old metadata first (foreign key constraint)
                    metadata_deleted = await conn.execute(f"""
                        DELETE FROM {self.metadata_table}
                        WHERE created_at < NOW() - INTERVAL '{older_than_days} days';
                    """)
                    
                    # Delete old checkpoints
                    checkpoints_deleted = await conn.execute(f"""
                        DELETE FROM {self.table_name}
                        WHERE created_at < NOW() - INTERVAL '{older_than_days} days';
                    """)
                    
                    deleted_count = int(checkpoints_deleted.split()[-1])
                    logger.info(f"Cleaned up {deleted_count} old checkpoints older than {older_than_days} days")
                    
                    return deleted_count
                    
        except Exception as e:
            logger.error(f"Failed to cleanup old checkpoints: {e}")
            raise

    async def get_active_workflows(self) -> List[Dict[str, Any]]:
        """Get list of currently active workflows."""
        if not self._initialized:
            await self.initialize()
            
        try:
            async with self._connection_pool.acquire() as conn:
                results = await conn.fetch(f"""
                    SELECT DISTINCT
                        c.thread_id,
                        m.workflow_name,
                        m.workflow_status,
                        c.created_at,
                        c.updated_at
                    FROM {self.table_name} c
                    LEFT JOIN {self.metadata_table} m ON c.thread_id = m.thread_id
                    WHERE m.workflow_status IN ('pending', 'running')
                    ORDER BY c.updated_at DESC;
                """)
                
                workflows = []
                for result in results:
                    workflows.append({
                        "thread_id": result["thread_id"],
                        "workflow_name": result["workflow_name"],
                        "status": result["workflow_status"],
                        "created_at": result["created_at"],
                        "updated_at": result["updated_at"]
                    })
                
                return workflows
                
        except Exception as e:
            logger.error(f"Failed to get active workflows: {e}")
            raise

    async def close(self) -> None:
        """Close the connection pool."""
        if self._connection_pool:
            await self._connection_pool.close()
            self._connection_pool = None
            self._initialized = False
            logger.info("PostgreSQL checkpoint system closed")

    def __repr__(self) -> str:
        return f"<PostgreSQLCheckpointer(table={self.table_name})>"