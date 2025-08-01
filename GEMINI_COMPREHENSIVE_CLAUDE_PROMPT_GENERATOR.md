# GEMINI CLI COMPREHENSIVE CLAUDE PROMPT GENERATOR

## MISSION OBJECTIVE FOR GEMINI CLI
You are the **Senior Debugging & Optimization Engineer** within the **ReAgent Optimized Agentic Development Stack**. Your mission is to create an extremely detailed, technically precise, and copy-paste ready prompt for Claude CLI that addresses the critical security vulnerabilities, architectural improvements, and production readiness requirements identified in your comprehensive ReAgent system analysis.

## STRATEGIC CONTEXT FROM YOUR ANALYSIS

### CRITICAL FINDINGS REQUIRING IMMEDIATE ACTION:
1. **🚨 MAJOR SECURITY VULNERABILITY**: Plain-text API keys in secrets directory
2. **🏗️ MISSING FRONTEND**: Referenced in docker-compose.yml but not present
3. **🧪 INSUFFICIENT TESTING**: Tests directory underpopulated for system complexity
4. **⚡ ERROR HANDLING**: CrewOrchestrator needs sophisticated recovery mechanisms
5. **📚 DOCUMENTATION GAPS**: Component-level documentation insufficient

### HIGH COMPLEXITY COMPONENTS IDENTIFIED:
- **src/agents**: Multi-agent CrewAI architecture with complex inter-agent workflows
- **src/core**: Performance-critical infrastructure (SQLAlchemy, Redis, Weaviate)

### CURRENT SYSTEM STATUS:
- Phase 2 (Weaviate Schema Initialization): ✅ COMPLETE
- Phase 3 (Production Finalization): 🔄 IN PROGRESS
- Claude CLI has successfully deployed vector schemas and monitoring
- System approaching production readiness but critical security/architecture issues remain

## DETAILED REQUIREMENTS FOR CLAUDE CLI PROMPT

### PRIMARY OBJECTIVE
Create a comprehensive, step-by-step prompt that guides Claude CLI through:
1. **Immediate Security Remediation** (CRITICAL PRIORITY)
2. **Architectural Improvements** based on your deep analysis
3. **Production Readiness Enhancements**
4. **Testing Infrastructure Expansion**
5. **Error Handling Sophistication**

### SPECIFIC TECHNICAL REQUIREMENTS

#### 1. SECURITY HARDENING (IMMEDIATE PRIORITY)
**Requirements for Claude CLI Implementation**:
```yaml
security_fixes:
  secrets_management:
    - Remove all plain-text API keys from secrets/ directory
    - Implement secure environment variable management
    - Create .env.example with placeholder values
    - Add secrets/ to .gitignore if not already present
    - Implement runtime secret validation
    
  api_key_security:
    - Audit all files for hardcoded API keys
    - Implement secure credential loading patterns
    - Add API key masking in logs
    - Create secure credential rotation procedures
    
  production_security:
    - Configure HTTPS/TLS for production deployment
    - Implement request rate limiting per IP
    - Add input validation and sanitization
    - Configure CORS policies appropriately
```

#### 2. CREWORKCHESTRATOR ENHANCEMENT
**Based on Your Architectural Analysis**:
```python
orchestrator_improvements:
  error_handling:
    - Implement sophisticated retry mechanisms with exponential backoff
    - Add circuit breaker patterns for external API failures
    - Create comprehensive error classification system
    - Implement graceful degradation for agent failures
    
  recovery_mechanisms:
    - Add agent health monitoring and auto-restart capabilities
    - Implement workflow state persistence for recovery
    - Create fallback execution paths for critical workflows
    - Add comprehensive logging for debugging complex failures
    
  performance_optimization:
    - Implement agent execution pooling
    - Add workflow execution metrics and monitoring
    - Optimize inter-agent communication patterns
    - Create performance benchmarking for agent workflows
```

#### 3. TESTING INFRASTRUCTURE EXPANSION
**Comprehensive Test Suite Requirements**:
```python
testing_requirements:
  unit_tests:
    - Test coverage for all agent classes and methods
    - Mock external API dependencies appropriately
    - Test error handling and edge cases
    - Validate data model integrity
    
  integration_tests:
    - End-to-end agent workflow testing
    - Database integration testing
    - External API integration testing
    - Vector database (Weaviate) integration testing
    
  performance_tests:
    - Load testing for 50+ concurrent users
    - Agent execution performance benchmarks
    - Database query performance validation
    - Memory usage and resource consumption testing
    
  security_tests:
    - API authentication and authorization testing
    - Input validation and sanitization testing
    - Rate limiting effectiveness testing
    - Security vulnerability scanning
```

#### 4. FRONTEND CODE RESOLUTION
**Address Missing Frontend Component**:
```yaml
frontend_requirements:
  investigation:
    - Analyze docker-compose.yml frontend references
    - Determine if frontend should be React, Vue, or other framework
    - Create basic frontend structure if missing
    - Implement API integration for frontend-backend communication
    
  implementation:
    - Create responsive UI for real estate professionals
    - Implement property search and filtering interfaces
    - Add buyer profile management screens
    - Create report visualization components
```

#### 5. DOCUMENTATION ENHANCEMENT
**Component-Level Documentation Requirements**:
```markdown
documentation_structure:
  api_documentation:
    - Complete OpenAPI/Swagger documentation
    - Endpoint usage examples and response schemas
    - Authentication and authorization guides
    
  agent_documentation:
    - Individual agent purpose and capabilities
    - Inter-agent communication patterns
    - Workflow orchestration documentation
    
  deployment_documentation:
    - Production deployment procedures
    - Environment configuration guides
    - Monitoring and maintenance procedures
```

## CLAUDE CLI PROMPT STRUCTURE REQUIREMENTS

### PROMPT ORGANIZATION
Your generated Claude CLI prompts must always include:

1. **EXECUTIVE SUMMARY** (50-100 words)
   - Always tell it to "USE SUBAGENTS PROACTIVELY and intelligently delegate tasks to at least 4 subagents"
   - Clear mission statement
   - Priority sequence
   - Expected outcomes

2. **IMMEDIATE ACTIONS** (CRITICAL PRIORITY)
   - Step-by-step security remediation
   - Specific file modifications required
   - Validation procedures

3. **ARCHITECTURAL IMPROVEMENTS** (HIGH PRIORITY)
   - CrewOrchestrator enhancements
   - Error handling implementations
   - Performance optimizations

4. **TESTING & VALIDATION** (HIGH PRIORITY)
   - Test suite expansion
   - Coverage requirements
   - Performance benchmarking

5. **DOCUMENTATION & FRONTEND** (MEDIUM PRIORITY)
   - Missing component resolution
   - Documentation improvements

6. **VALIDATION CHECKPOINTS**
   - Success criteria for each phase
   - Testing procedures
   - Performance metrics

### TECHNICAL PRECISION REQUIREMENTS

#### Code Examples Must Include:
- **Exact file paths** for all modifications
- **Complete code snippets** with proper imports
- **Configuration examples** with realistic values
- **Error handling patterns** with specific exception types
- **Testing examples** with assertion patterns

#### Implementation Guidance Must Include:
- **Step-by-step procedures** with command examples
- **Dependency requirements** with version specifications
- **Environment setup** instructions
- **Validation commands** to verify implementations

### STRATEGIC COORDINATION REQUIREMENTS

#### Integration with ReAgent Stack:
- **Cascade IDE Oversight**: Include checkpoints for strategic review
- **Gemini CLI Follow-up**: Identify areas requiring your deeper analysis
- **Production Readiness**: Align with enterprise-grade objectives

#### Success Metrics Definition:
```yaml
success_criteria:
  security:
    - Zero plain-text secrets in repository
    - All API keys properly secured
    - Security audit passes with no critical issues
    
  performance:
    - System handles 50+ concurrent users
    - Response times <2s under load
    - Agent workflows complete within SLA
    
  reliability:
    - 99.9% uptime capability demonstrated
    - Error recovery mechanisms functional
    - Comprehensive monitoring operational
    
  testing:
    - >80% code coverage achieved
    - All integration tests passing
    - Performance benchmarks documented
```

## DELIVERABLE SPECIFICATIONS

### CLAUDE CLI PROMPT OUTPUT REQUIREMENTS:
1. **Length**: 3000-5000 words (comprehensive but actionable)
2. **Format**: Markdown with clear section headers
3. **Code Examples**: Minimum 20 code snippets with full context
4. **Commands**: All terminal commands copy-paste ready
5. **Validation**: Clear success/failure criteria for each step

### PROMPT EFFECTIVENESS CRITERIA:
- **Actionable**: Claude can execute immediately without clarification
- **Comprehensive**: Addresses all critical issues from your analysis
- **Prioritized**: Clear sequence from critical to medium priority
- **Measurable**: Specific success metrics and validation procedures
- **Strategic**: Aligns with ReAgent enterprise-grade objectives

## EXECUTION INSTRUCTIONS FOR GEMINI CLI

1. **Analyze Current State**: Review your comprehensive ReAgent analysis
2. **Prioritize Issues**: Sequence by criticality (security → architecture → testing)
3. **Design Solutions**: Create specific, implementable solutions for each issue
4. **Generate Prompt**: Create detailed, copy-paste ready Claude CLI prompt
5. **Validate Completeness**: Ensure all critical findings are addressed

## SUCCESS VALIDATION

Your generated Claude CLI prompt is successful if:
- ✅ Addresses all 5 critical findings from your analysis
- ✅ Provides specific, actionable implementation steps
- ✅ Includes comprehensive code examples and commands
- ✅ Defines clear success criteria and validation procedures
- ✅ Maintains strategic alignment with ReAgent enterprise objectives
- ✅ Enables Claude CLI to execute without additional clarification

## STRATEGIC IMPORTANCE

This prompt represents the critical bridge between your deep architectural analysis and Claude CLI's rapid implementation capabilities. The quality and precision of this prompt directly impacts:
- **ReAgent Security Posture**: Elimination of critical vulnerabilities
- **Production Readiness**: Achievement of enterprise-grade reliability
- **Development Velocity**: Efficient coordination between analysis and implementation
- **System Quality**: Long-term scalability and maintainability

**Generate the most comprehensive, technically precise, and immediately actionable Claude CLI prompt possible. The success of ReAgent's production deployment depends on the quality of this coordination between our development stack layers.**

---

**EXECUTE WITH MAXIMUM PRECISION AND TECHNICAL DEPTH. THIS IS THE CRITICAL COORDINATION POINT FOR REAGENT'S PRODUCTION SUCCESS.** 🎯
