import os
from flask import Blueprint, request, jsonify, render_template

ai_agent_bp = Blueprint("ai_agent", __name__, url_prefix="/ai-agent")

@ai_agent_bp.route("/")
def agent_dashboard():
    return render_template("ai_agent.html")

@ai_agent_bp.route("/api/run", methods=["POST"])
def run_agent():
    data = request.json or {}
    instruction = data.get("instruction")
    
    if not instruction:
        return jsonify({"status": "error", "message": "Instruction is required"}), 400
        
    try:
        # Lazy load dependencies to prevent circular imports if any
        from vector_store.vector_index import VectorIndex
        from ai_agents.planner import PlannerAgent
        from ai_agents.coder_agent import CoderAgent
        from ai_agents.debugger_agent import DebuggerAgent
        
        # Initialize components
        v_index = VectorIndex()
        planner = PlannerAgent()
        coder = CoderAgent()
        debugger = DebuggerAgent()
        
        full_logs = []
        
        # 1. Retrieve relevant code using vector search
        full_logs.append("Phase 1: Retrieving context from vector store...")
        context = v_index.search(instruction, top_k=5)
        full_logs.append(f"Retrieved {len(context)} relevant code snippets.")
        
        # 2. Generate execution plan
        full_logs.append("Phase 2: Generating execution plan...")
        plan = planner.generate_plan(instruction, context)
        full_logs.append(f"Plan generated with {len(plan.get('steps', []))} steps.")
        
        # 3 & 4. Execute file changes and run verification commands
        full_logs.append("Phase 3 & 4: Executing file changes and commands...")
        execution_result = coder.execute_plan(plan, instruction)
        
        full_logs.extend(execution_result["logs"])
        files_modified = execution_result["files_modified"]
        actions_executed = execution_result["actions_executed"]
        failed_commands = execution_result.get("failed_commands", [])
        
        # 5. If failure occurs, trigger debugger_agent
        full_logs.append("Phase 5: Checking for command failures...")
        for failed in failed_commands:
            cmd = failed["command"]
            stderr = failed["stderr"]
            
            full_logs.append(f"Triggering DebuggerAgent for failed command: {cmd}")
            debug_logs = debugger.debug_loop(cmd, stderr, instruction)
            full_logs.extend(debug_logs["logs"])
            
        # 6. Return structured output
        return jsonify({
            "status": "success",
            "plan": plan.get("steps", []),
            "actions_executed": actions_executed,
            "files_modified": files_modified,
            "logs": full_logs
        }), 200
        
    except Exception as e:
        import traceback
        return jsonify({
            "status": "error",
            "message": str(e),
            "traceback": traceback.format_exc(),
            "logs": ["Fatal error inside agent execution."]
        }), 500
