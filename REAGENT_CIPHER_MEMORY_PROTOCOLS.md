# ReAgent Cipher Memory Protocols

## Overview
This document defines the shared memory protocols for the ReAgent Agentic Development Stack using Cipher as the unified memory layer across Cascade IDE, Claude CLI, and Gemini CLI.

## Memory Architecture

### Core Principles
- **Unified Context**: All agents share the same memory store for project continuity
- **Role-Based Access**: Each agent focuses on memories relevant to their specialization  
- **Automatic Capture**: Critical events and decisions are automatically stored
- **Cross-Agent Handoffs**: Context preservation during agent transitions

### Memory Collections

#### 1. Architecture Collection
- **Purpose**: Track architectural decisions, design patterns, system structure
- **Retention**: Permanent
- **Primary Users**: Gemini CLI (architectural review), Cascade (oversight)
- **Auto-Store Triggers**:
  - Directory structure changes
  - Import path refactoring
  - Module reorganization
  - Design pattern implementations

#### 2. Bugs and Fixes Collection  
- **Purpose**: Bug reports, solutions, debugging context
- **Retention**: 6 months
- **Primary Users**: All agents
- **Auto-Store Triggers**:
  - Error discoveries
  - Solution implementations
  - Debugging sessions
  - Performance issues

#### 3. API Integration Collection
- **Purpose**: API keys, integration status, external service configurations
- **Retention**: Permanent
- **Primary Users**: Claude CLI (integration work), Cascade (coordination)
- **Auto-Store Triggers**:
  - API key updates
  - Integration completions
  - Service configurations
  - Rate limiting issues

#### 4. Development Progress Collection
- **Purpose**: Feature development, refactoring progress, milestone tracking
- **Retention**: 3 months
- **Primary Users**: All agents
- **Auto-Store Triggers**:
  - Feature completions
  - Milestone achievements
  - Refactoring phases
  - Testing results

#### 5. Agent Coordination Collection
- **Purpose**: Inter-agent communication, handoffs, coordination protocols
- **Retention**: 1 month
- **Primary Users**: Cascade (coordination), all agents
- **Auto-Store Triggers**:
  - Agent handoffs
  - Coordination decisions
  - Workflow transitions
  - Communication protocols

## Agent-Specific Memory Protocols

### Cascade IDE (Senior Overseeing Developer)
**Role**: Strategic oversight, coordination, quality assurance

**Memory Focus**:
- Architecture decisions and reviews
- Agent coordination protocols
- Quality assurance checkpoints
- Project milestones and planning

**Auto-Store Events**:
- Strategic decisions made
- Agent coordination initiated
- Quality issues identified
- Plan updates and revisions

### Claude CLI (Frontline Hands-On Developer)
**Role**: Rapid iteration, coding, deployment

**Memory Focus**:
- Development progress tracking
- Bug fixes and solutions
- API integration status
- Code implementation details

**Auto-Store Events**:
- Code changes committed
- Bugs discovered and fixed
- Integrations completed
- Deployment status updates

### Gemini CLI (Senior Debugging & Optimization Engineer)
**Role**: Deep analysis, architectural review, optimization

**Memory Focus**:
- Architectural improvements
- Performance optimizations
- Deep debugging insights
- Code quality enhancements

**Auto-Store Events**:
- Architectural refactoring
- Performance improvements
- Complex bug resolutions
- Optimization insights

## Memory Query Patterns

### Context Retrieval
```bash
# Get recent architectural decisions
cipher_memory_search collection:"architecture" query:"import path refactoring" limit:5

# Find bug fix patterns
cipher_memory_search collection:"bugs_and_fixes" query:"session management" limit:10

# Check API integration status
cipher_memory_search collection:"api_integration" query:"OpenAI Weaviate CoreLogic" limit:3
```

### Cross-Agent Handoffs
```bash
# Store handoff context
cipher_extract_and_operate_memory action:"store" collection:"agent_coordination" 
content:"Gemini completed import refactoring, ready for Claude production deployment"

# Retrieve handoff context
cipher_memory_search collection:"agent_coordination" query:"handoff deployment" limit:1
```

## Memory Templates

### Architectural Decision Template
```yaml
type: "architectural_decision"
timestamp: "YYYY-MM-DD HH:MM:SS"
agent: "Cascade|Claude|Gemini"
decision: "Brief description"
rationale: "Why this decision was made"
impact: "Expected impact on system"
files_affected: ["list", "of", "files"]
related_memories: ["memory_id_1", "memory_id_2"]
```

### Bug Fix Template
```yaml
type: "bug_fix"
timestamp: "YYYY-MM-DD HH:MM:SS" 
agent: "Cascade|Claude|Gemini"
bug_description: "What was the issue"
root_cause: "Why it occurred"
solution: "How it was fixed"
files_modified: ["list", "of", "files"]
test_results: "Verification status"
related_memories: ["memory_id_1", "memory_id_2"]
```

### Integration Status Template
```yaml
type: "api_integration"
timestamp: "YYYY-MM-DD HH:MM:SS"
agent: "Cascade|Claude|Gemini"
service: "OpenAI|Weaviate|CoreLogic|Domain|REA|NSW_LPI"
status: "configured|testing|operational|pending"
configuration: "Key config details"
issues: "Any problems encountered"
next_steps: "What needs to be done"
related_memories: ["memory_id_1", "memory_id_2"]
```

## Usage Examples

### 1. Starting New Development Session
```bash
# Query recent progress
cipher_memory_search query:"recent development progress" limit:5

# Get current integration status  
cipher_memory_search collection:"api_integration" query:"status operational" limit:10

# Check for pending issues
cipher_memory_search collection:"bugs_and_fixes" query:"unresolved pending" limit:5
```

### 2. Agent Handoff Process
```bash
# Store completion status
cipher_extract_and_operate_memory action:"store" collection:"agent_coordination"
content:"Claude completed Phase 2 Weaviate schema deployment. All 4 subagents successful. Ready for Gemini architectural review."

# Query handoff context
cipher_memory_search collection:"agent_coordination" query:"Phase 2 complete" limit:1
```

### 3. Debugging Session
```bash
# Find similar issues
cipher_memory_search collection:"bugs_and_fixes" query:"import path session management" limit:10

# Store debugging insights
cipher_extract_and_operate_memory action:"store" collection:"bugs_and_fixes"
content:"Import path issue resolved by switching from src.agents.* to reagent.* pattern. Critical for production deployment."
```

## Integration Commands

### Initialize Cipher for Session
```bash
cd /home/emergence-admin/memAgent
cipher --agent cipher.yml
```

### Start MCP Server Mode
```bash
cipher --mode mcp --agent /home/emergence-admin/memAgent/cipher.yml
```

### CLI Integration Commands (for Claude/Gemini)
```bash
# Load ReAgent memory context
cipher_memory_search query:"ReAgent current status" collection:"development_progress" limit:5

# Store critical decisions
cipher_extract_and_operate_memory action:"store" collection:"architecture" 
content:"Your memory content here"
```

This protocol ensures seamless context preservation and coordination across all three agents in the ReAgent Agentic Development Stack.
