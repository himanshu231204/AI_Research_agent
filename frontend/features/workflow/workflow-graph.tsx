'use client';

import { useEffect, useState, useCallback } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useWorkflowStore, useResearchStore } from '@/stores';
import { cn, getAgentDisplayName, getAgentIcon } from '@/lib/utils';
import type { WorkflowNode, WorkflowEdge, AgentName, AgentStatus } from '@/types';
import {
  ArrowRight,
  RefreshCw,
  GitBranch,
  Loader2,
  CheckCircle,
  XCircle,
  Clock,
} from 'lucide-react';

// Define the workflow nodes based on the LangGraph structure
const defaultNodes: WorkflowNode[] = [
  { id: 'start', name: 'Start', type: 'planner', status: 'idle', position: { x: 0, y: 0 } },
  { id: 'planner', name: 'Planner', type: 'planner', status: 'idle', position: { x: 200, y: 0 } },
  { id: 'task_router', name: 'Task Router', type: 'task_router', status: 'idle', position: { x: 400, y: 0 } },
  { id: 'research', name: 'Research Workers', type: 'web_research', status: 'idle', position: { x: 600, y: 0 } },
  { id: 'aggregator', name: 'Aggregator', type: 'writer', status: 'idle', position: { x: 800, y: 0 } },
  { id: 'reflection', name: 'Reflection', type: 'reflection', status: 'idle', position: { x: 600, y: 100 } },
  { id: 'writer', name: 'Writer', type: 'writer', status: 'idle', position: { x: 800, y: 100 } },
  { id: 'citation', name: 'Citation', type: 'citation', status: 'idle', position: { x: 1000, y: 100 } },
  { id: 'end', name: 'End', type: 'writer', status: 'idle', position: { x: 1200, y: 100 } },
];

const defaultEdges: WorkflowEdge[] = [
  { id: 'e1', source: 'start', target: 'planner', type: 'default' },
  { id: 'e2', source: 'planner', target: 'task_router', type: 'default' },
  { id: 'e3', source: 'task_router', target: 'research', type: 'default' },
  { id: 'e4', source: 'research', target: 'aggregator', type: 'default' },
  { id: 'e5', source: 'aggregator', target: 'reflection', type: 'default' },
  { id: 'e6', source: 'reflection', target: 'writer', type: 'reflection', animated: true },
  { id: 'e7', source: 'writer', target: 'citation', type: 'default' },
  { id: 'e8', source: 'citation', target: 'end', type: 'default' },
];

export function WorkflowGraph() {
  const { workflow, setWorkflow, setCurrentNode, setProgress, setStatus } = useWorkflowStore();
  const { status, currentAgent, progress } = useResearchStore();
  const [nodes, setNodes] = useState<WorkflowNode[]>(defaultNodes);
  const [edges, setEdges] = useState<WorkflowEdge[]>(defaultEdges);

  // Map status to node activation
  useEffect(() => {
    const statusNodeMap: Record<string, string[]> = {
      planning: ['planner'],
      researching: ['task_router', 'research'],
      reflecting: ['reflection'],
      writing: ['writer', 'citation'],
      completed: ['end'],
    };

    const activeNodes = statusNodeMap[status] || [];
    
    setNodes((prev) =>
      prev.map((node) => ({
        ...node,
        status: activeNodes.includes(node.id)
          ? 'running'
          : activeNodes.includes(node.id.split('_')[0])
          ? 'completed'
          : 'idle',
      }))
    );

    // Update edges based on current node
    if (currentAgent) {
      const nodeIndex = nodes.findIndex((n) => n.name.toLowerCase().includes(currentAgent.replace('_', ' ')));
      if (nodeIndex >= 0) {
        setEdges((prev) =>
          prev.map((edge, i) => ({
            ...edge,
            animated: i === nodeIndex,
          }))
        );
      }
    }
  }, [status, currentAgent]);

  const getNodeStatusColor = (nodeStatus: AgentStatus) => {
    switch (nodeStatus) {
      case 'running':
        return 'border-blue-500 bg-blue-500/10';
      case 'completed':
        return 'border-green-500 bg-green-500/10';
      case 'failed':
        return 'border-red-500 bg-red-500/10';
      default:
        return 'border-muted bg-muted/50';
    }
  };

  const getEdgeTypeIcon = (edgeType: string) => {
    switch (edgeType) {
      case 'reflection':
        return <RefreshCw className="h-3 w-3 text-orange-500" />;
      case 'retry':
        return <RefreshCw className="h-3 w-3 text-yellow-500" />;
      case 'fallback':
        return <GitBranch className="h-3 w-3 text-purple-500" />;
      default:
        return null;
    }
  };

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Workflow Visualization</h2>
        <Badge variant="outline" className="gap-1">
          <Loader2 className="h-3 w-3 animate-spin" />
          {Math.round(progress * 100)}%
        </Badge>
      </div>

      {/* Progress Bar */}
      <Card>
        <CardContent className="p-4">
          <div className="flex items-center justify-between text-sm">
            <span className="text-muted-foreground">Overall Progress</span>
            <span className="font-medium">{Math.round(progress * 100)}%</span>
          </div>
          <div className="mt-2 h-2 w-full rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all duration-500"
              style={{ width: `${progress * 100}%` }}
            />
          </div>
        </CardContent>
      </Card>

      {/* Workflow Graph */}
      <Card className="flex-1">
        <CardContent className="h-full p-4">
          <ScrollArea className="h-full">
            <div className="relative min-w-[1000px] py-8">
              {/* Nodes */}
              <div className="flex items-center justify-between">
                {nodes.map((node, index) => (
                  <div key={node.id} className="flex items-center">
                    <div
                      className={cn(
                        'flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-all',
                        getNodeStatusColor(node.status),
                        node.status === 'running' && 'animate-pulse'
                      )}
                    >
                      <div className="text-2xl">{getAgentIcon(node.type)}</div>
                      <div className="text-center">
                        <p className="font-medium">{node.name}</p>
                        <p className="text-xs text-muted-foreground">{node.status}</p>
                      </div>
                      {node.status === 'running' && (
                        <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
                      )}
                      {node.status === 'completed' && (
                        <CheckCircle className="h-4 w-4 text-green-500" />
                      )}
                      {node.status === 'failed' && (
                        <XCircle className="h-4 w-4 text-red-500" />
                      )}
                    </div>

                    {/* Edge */}
                    {index < nodes.length - 1 && (
                      <div className="flex items-center px-2">
                        <div
                          className={cn(
                            'h-0.5 w-8',
                            nodes[index + 1].status !== 'idle'
                              ? 'bg-primary'
                              : 'bg-muted'
                          )}
                        />
                        {edges[index] && edges[index].type !== 'default' && (
                          <div className="mx-1">
                            {getEdgeTypeIcon(edges[index].type)}
                          </div>
                        )}
                        <div
                          className={cn(
                            'h-0.5 w-8',
                            nodes[index + 1].status !== 'idle'
                              ? 'bg-primary'
                              : 'bg-muted'
                          )}
                        />
                      </div>
                    )}
                  </div>
                ))}
              </div>

              {/* Reflection Loop Indicator */}
              {status === 'reflecting' && (
                <div className="mt-4 flex items-center justify-center">
                  <div className="flex items-center gap-2 rounded-full border border-orange-500 bg-orange-500/10 px-4 py-2">
                    <RefreshCw className="h-4 w-4 animate-spin text-orange-500" />
                    <span className="text-sm text-orange-500">Reflection Loop Active</span>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Legend */}
      <Card>
        <CardContent className="flex items-center justify-between p-4">
          <div className="flex items-center gap-4">
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-gray-400" />
              <span className="text-sm">Idle</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-blue-500 animate-pulse" />
              <span className="text-sm">Running</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-green-500" />
              <span className="text-sm">Completed</span>
            </div>
            <div className="flex items-center gap-2">
              <div className="h-3 w-3 rounded-full bg-red-500" />
              <span className="text-sm">Failed</span>
            </div>
          </div>
          <div className="flex items-center gap-2">
            <RefreshCw className="h-3 w-3 text-orange-500" />
            <span className="text-sm text-muted-foreground">Reflection Edge</span>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}

export default WorkflowGraph;