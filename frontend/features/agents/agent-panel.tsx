'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Progress } from '@/components/ui/progress';
import { useAgentsStore, useResearchStore } from '@/stores';
import { cn, formatDuration, getAgentDisplayName, getAgentIcon } from '@/lib/utils';
import type { Agent, AgentStatus, AgentName } from '@/types';
import {
  Brain,
  Clock,
  Zap,
  AlertTriangle,
  CheckCircle,
  Loader2,
  Pause,
  Play,
} from 'lucide-react';

const defaultAgents: Agent[] = [
  { id: 'planner', name: 'planner', status: 'idle' },
  { id: 'task_router', name: 'task_router', status: 'idle' },
  { id: 'web_research', name: 'web_research', status: 'idle' },
  { id: 'github_analysis', name: 'github_analysis', status: 'idle' },
  { id: 'pdf_rag', name: 'pdf_rag', status: 'idle' },
  { id: 'browser_automation', name: 'browser_automation', status: 'idle' },
  { id: 'memory', name: 'memory', status: 'idle' },
  { id: 'reflection', name: 'reflection', status: 'idle' },
  { id: 'writer', name: 'writer', status: 'idle' },
  { id: 'citation', name: 'citation', status: 'idle' },
];

export function AgentPanel() {
  const { agents, setAgents } = useAgentsStore();
  const { currentAgent, status } = useResearchStore();
  const [localAgents, setLocalAgents] = useState<Agent[]>(defaultAgents);

  useEffect(() => {
    // Update agent status based on current research status
    if (currentAgent) {
      setLocalAgents((prev) =>
        prev.map((agent) => ({
          ...agent,
          status: agent.name === currentAgent ? 'running' : agent.status,
        }))
      );
    }
  }, [currentAgent]);

  const getStatusIcon = (agentStatus: AgentStatus) => {
    switch (agentStatus) {
      case 'running':
        return <Loader2 className="h-4 w-4 animate-spin text-blue-500" />;
      case 'completed':
        return <CheckCircle className="h-4 w-4 text-green-500" />;
      case 'failed':
        return <AlertTriangle className="h-4 w-4 text-red-500" />;
      case 'waiting':
        return <Pause className="h-4 w-4 text-yellow-500" />;
      default:
        return <div className="h-2 w-2 rounded-full bg-gray-400" />;
    }
  };

  const getStatusColor = (agentStatus: AgentStatus) => {
    switch (agentStatus) {
      case 'running':
        return 'bg-blue-500';
      case 'completed':
        return 'bg-green-500';
      case 'failed':
        return 'bg-red-500';
      case 'waiting':
        return 'bg-yellow-500';
      default:
        return 'bg-gray-400';
    }
  };

  const activeAgents = localAgents.filter((a) => a.status === 'running');
  const completedAgents = localAgents.filter((a) => a.status === 'completed');
  const failedAgents = localAgents.filter((a) => a.status === 'failed');

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Active Agents</h2>
        <Badge variant="outline">
          {activeAgents.length} / {localAgents.length} active
        </Badge>
      </div>

      {/* Status Summary */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-blue-500/10 p-2">
              <Zap className="h-4 w-4 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{activeAgents.length}</p>
              <p className="text-xs text-muted-foreground">Running</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-green-500/10 p-2">
              <CheckCircle className="h-4 w-4 text-green-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{completedAgents.length}</p>
              <p className="text-xs text-muted-foreground">Completed</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-red-500/10 p-2">
              <AlertTriangle className="h-4 w-4 text-red-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{failedAgents.length}</p>
              <p className="text-xs text-muted-foreground">Failed</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Agent List */}
      <ScrollArea className="flex-1">
        <div className="space-y-2">
          {localAgents.map((agent) => (
            <Card
              key={agent.id}
              className={cn(
                'transition-colors',
                agent.status === 'running' && 'border-blue-500 bg-blue-500/5'
              )}
            >
              <CardContent className="flex items-center gap-4 p-3">
                <div className="flex h-10 w-10 items-center justify-center rounded-lg bg-muted">
                  <span className="text-lg">{getAgentIcon(agent.name)}</span>
                </div>

                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{getAgentDisplayName(agent.name)}</p>
                    {getStatusIcon(agent.status)}
                  </div>
                  {agent.current_task && (
                    <p className="text-sm text-muted-foreground truncate">
                      {agent.current_task}
                    </p>
                  )}
                </div>

                <div className="flex items-center gap-4 text-sm text-muted-foreground">
                  {agent.duration_ms && (
                    <div className="flex items-center gap-1">
                      <Clock className="h-3 w-3" />
                      {formatDuration(agent.duration_ms)}
                    </div>
                  )}
                  {agent.token_usage && (
                    <div className="flex items-center gap-1">
                      <Brain className="h-3 w-3" />
                      {agent.token_usage.total_tokens.toLocaleString()}
                    </div>
                  )}
                </div>

                <div className={cn('h-2 w-2 rounded-full', getStatusColor(agent.status))} />
              </CardContent>
            </Card>
          ))}
        </div>
      </ScrollArea>

      {/* Current Activity */}
      {currentAgent && (
        <Card className="border-blue-500 bg-blue-500/5">
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium">Current Activity</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-3">
              <Loader2 className="h-4 w-4 animate-spin text-blue-500" />
              <span className="font-medium">{getAgentDisplayName(currentAgent)}</span>
              <Badge variant="secondary" className="ml-auto">
                {status}
              </Badge>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  );
}

export default AgentPanel;