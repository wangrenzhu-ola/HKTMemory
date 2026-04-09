"""
MCP Server for HKT-Memory v4

Supports Model Context Protocol for integration with Claude, Cursor, etc.
"""

import json
import asyncio
from typing import Dict, List, Any, Optional
from pathlib import Path

from .tools import MemoryTools


class MemoryMCPServer:
    """
    HKT-Memory MCP Server
    
    Provides 9 MCP tools for memory management.
    """
    
    def __init__(self, memory_dir: str = "memory"):
        self.memory_dir = Path(memory_dir)
        self.tools = MemoryTools(self.memory_dir)
        self._running = False
    
    def handle_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Handle MCP request
        
        Args:
            request: MCP request with 'tool' and 'params'
            
        Returns:
            MCP response
        """
        tool_name = request.get("tool")
        params = request.get("params", {})
        
        # Tool routing
        tool_map = {
            "memory_recall": self.tools.memory_recall,
            "memory_store": self.tools.memory_store,
            "memory_forget": self.tools.memory_forget,
            "memory_update": self.tools.memory_update,
            "memory_stats": self.tools.memory_stats,
            "memory_list": self.tools.memory_list,
            "self_improvement_log": self.tools.self_improvement_log,
            "self_improvement_extract_skill": self.tools.self_improvement_extract_skill,
            "self_improvement_review": self.tools.self_improvement_review,
        }
        
        if tool_name not in tool_map:
            return {
                "success": False,
                "error": f"Unknown tool: {tool_name}",
                "available_tools": list(tool_map.keys())
            }
        
        try:
            result = tool_map[tool_name](**params)
            return {
                "success": True,
                "tool": tool_name,
                "result": result
            }
        except Exception as e:
            return {
                "success": False,
                "tool": tool_name,
                "error": str(e)
            }
    
    def get_capabilities(self) -> Dict[str, Any]:
        """Get server capabilities"""
        return {
            "name": "HKT-Memory v4",
            "version": "4.0.0",
            "tools": [
                {
                    "name": "memory_recall",
                    "description": "Recall relevant memories based on query",
                    "parameters": {
                        "query": {"type": "string", "required": True},
                        "layer": {"type": "string", "default": "all"},
                        "limit": {"type": "integer", "default": 5}
                    }
                },
                {
                    "name": "memory_store",
                    "description": "Store new memory",
                    "parameters": {
                        "content": {"type": "string", "required": True},
                        "title": {"type": "string", "default": ""},
                        "layer": {"type": "string", "default": "L2"},
                        "topic": {"type": "string", "default": "general"},
                        "importance": {"type": "string", "default": "medium"}
                    }
                },
                {
                    "name": "memory_forget",
                    "description": "Delete a memory",
                    "parameters": {
                        "memory_id": {"type": "string", "required": True},
                        "layer": {"type": "string", "default": "L2"}
                    }
                },
                {
                    "name": "memory_update",
                    "description": "Update existing memory",
                    "parameters": {
                        "memory_id": {"type": "string", "required": True},
                        "content": {"type": "string"},
                        "layer": {"type": "string", "default": "L2"}
                    }
                },
                {
                    "name": "memory_stats",
                    "description": "Get memory statistics",
                    "parameters": {}
                },
                {
                    "name": "memory_list",
                    "description": "List memories",
                    "parameters": {
                        "layer": {"type": "string", "default": "L2"},
                        "topic": {"type": "string"},
                        "limit": {"type": "integer", "default": 20}
                    }
                },
                {
                    "name": "self_improvement_log",
                    "description": "Log learning or error",
                    "parameters": {
                        "log_type": {"type": "string", "required": True},
                        "content": {"type": "string", "required": True},
                        "category": {"type": "string"}
                    }
                },
                {
                    "name": "self_improvement_extract_skill",
                    "description": "Extract skill from learning",
                    "parameters": {
                        "learning_id": {"type": "string", "required": True}
                    }
                },
                {
                    "name": "self_improvement_review",
                    "description": "Review improvement status",
                    "parameters": {}
                }
            ]
        }
    
    def start_stdio(self):
        """Start server in stdio mode (for MCP)"""
        import sys
        
        self._running = True
        
        while self._running:
            try:
                line = sys.stdin.readline()
                if not line:
                    break
                
                request = json.loads(line)
                response = self.handle_request(request)
                
                print(json.dumps(response), flush=True)
                
            except json.JSONDecodeError as e:
                print(json.dumps({
                    "success": False,
                    "error": f"Invalid JSON: {e}"
                }), flush=True)
            except Exception as e:
                print(json.dumps({
                    "success": False,
                    "error": str(e)
                }), flush=True)
    
    def start_http(self, host: str = "127.0.0.1", port: int = 8000):
        """Start HTTP server"""
        try:
            from flask import Flask, request, jsonify
            
            app = Flask(__name__)
            
            @app.route('/')
            def index():
                return jsonify(self.get_capabilities())
            
            @app.route('/tools/<tool_name>', methods=['POST'])
            def call_tool(tool_name):
                params = request.get_json() or {}
                response = self.handle_request({
                    "tool": tool_name,
                    "params": params
                })
                return jsonify(response)
            
            @app.route('/mcp', methods=['POST'])
            def mcp_endpoint():
                req = request.get_json()
                response = self.handle_request(req)
                return jsonify(response)
            
            print(f"Starting HKT-Memory MCP server on {host}:{port}")
            app.run(host=host, port=port, debug=False)
            
        except ImportError:
            print("Flask not installed. Install with: pip install flask")
            raise


def main():
    """CLI entry point"""
    import argparse
    
    parser = argparse.ArgumentParser(description="HKT-Memory MCP Server")
    parser.add_argument("--memory-dir", default="memory", help="Memory directory")
    parser.add_argument("--mode", choices=["stdio", "http"], default="stdio", help="Server mode")
    parser.add_argument("--host", default="127.0.0.1", help="HTTP host")
    parser.add_argument("--port", type=int, default=8000, help="HTTP port")
    
    args = parser.parse_args()
    
    server = MemoryMCPServer(args.memory_dir)
    
    if args.mode == "stdio":
        server.start_stdio()
    else:
        server.start_http(args.host, args.port)


if __name__ == "__main__":
    main()
