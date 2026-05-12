'use client';

import { useEffect, useState } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ScrollArea } from '@/components/ui/scroll-area';
import { useTimelineStore, useResearchStore } from '@/stores';
import { cn, formatTime, getAgentDisplayName, getAgentIcon } from '@/lib/utils';
import type { TimelineEvent, TimelineEventType } from '@/types';
import {
  Search,
  Globe,
  RefreshCw,
  Brain,
  FileText,
  AlertCircle,
  Play,
  CheckCircle,
  XCircle,
  Clock,
} from 'lucide-react';

const eventTypeIcons: Record<TimelineEventType, React.ReactNode> = {
  search: <Search className="h-4 w-4" />,
  browser_action: <Globe className="h-4 w-4" />,
  reflection: <RefreshCw className="h-4 w-4" />,
  model_routing: <Brain className="h-4 w-4" />,
  citation: <FileText className="h-4 w-4" />,
  artifact: <FileText className="h-4 w-4" />,
  error: <AlertCircle className="h-4 w-4" />,
  task_start: <Play className="h-4 w-4" />,
  task_complete: <CheckCircle className="h-4 w-4" />,
};

const eventTypeColors: Record<TimelineEventType, string> = {
  search: 'bg-blue-500',
  browser_action: 'bg-purple-500',
  reflection: 'bg-orange-500',
  model_routing: 'bg-cyan-500',
  citation: 'bg-green-500',
  artifact: 'bg-yellow-500',
  error: 'bg-red-500',
  task_start: 'bg-blue-500',
  task_complete: 'bg-green-500',
};

export function ResearchTimeline() {
  const { events, addEvent, clearEvents } = useTimelineStore();
  const { status, currentAgent } = useResearchStore();
  const [localEvents, setLocalEvents] = useState<TimelineEvent[]>([]);

  // Add events based on status changes
  useEffect(() => {
    if (currentAgent) {
      const newEvent: TimelineEvent = {
        id: `event-${Date.now()}`,
        type: 'task_start',
        agent: currentAgent as any,
        message: `Started: ${getAgentDisplayName(currentAgent)}`,
        timestamp: new Date().toISOString(),
      };
      setLocalEvents((prev) => [newEvent, ...prev].slice(0, 50));
    }
  }, [currentAgent]);

  // Add sample events for demo
  useEffect(() => {
    if (status === 'researching' && localEvents.length === 0) {
      const sampleEvents: TimelineEvent[] = [
        {
          id: '1',
          type: 'task_start',
          agent: 'planner',
          message: 'Planning research strategy',
          timestamp: new Date(Date.now() - 30000).toISOString(),
        },
        {
          id: '2',
          type: 'model_routing',
          agent: 'planner',
          message: 'Selected model: qwen3 (local)',
          timestamp: new Date(Date.now() - 25000).toISOString(),
        },
        {
          id: '3',
          type: 'task_complete',
          agent: 'planner',
          message: 'Plan generated with 5 research tasks',
          timestamp: new Date(Date.now() - 20000).toISOString(),
        },
        {
          id: '4',
          type: 'search',
          agent: 'web_research',
          message: 'Searching: quantum computing developments 2024',
          timestamp: new Date(Date.now() - 15000).toISOString(),
        },
        {
          id: '5',
          type: 'search',
          agent: 'web_research',
          message: 'Found 12 relevant sources',
          timestamp: new Date(Date.now() - 10000).toISOString(),
        },
        {
          id: '6',
          type: 'citation',
          agent: 'citation',
          message: 'Added 8 citations to research',
          timestamp: new Date(Date.now() - 5000).toISOString(),
        },
      ];
      setLocalEvents(sampleEvents);
    }
  }, [status]);

  const getEventColor = (type: TimelineEventType) => {
    return eventTypeColors[type] || 'bg-gray-500';
  };

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Research Timeline</h2>
        <Badge variant="outline">
          {localEvents.length} events
        </Badge>
      </div>

      <Card className="flex-1">
        <CardContent className="p-0">
          <ScrollArea className="h-[500px] p-4">
            <div className="relative">
              {/* Timeline line */}
              <div className="absolute left-4 top-0 bottom-0 w-0.5 bg-border" />

              {/* Events */}
              <div className="space-y-4">
                {localEvents.length === 0 ? (
                  <div className="flex flex-col items-center justify-center py-12 text-center">
                    <Clock className="mb-2 h-8 w-8 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      No events yet. Start a research task to see the timeline.
                    </p>
                  </div>
                ) : (
                  localEvents.map((event, index) => (
                    <div
                      key={event.id}
                      className={cn(
                        'relative flex gap-4 pl-8',
                        index === 0 && 'animate-fade-in'
                      )}
                    >
                      {/* Timeline dot */}
                      <div
                        className={cn(
                          'absolute left-2 top-2 flex h-4 w-4 items-center justify-center rounded-full',
                          getEventColor(event.type)
                        )}
                      >
                        <div className="h-2 w-2 rounded-full bg-white" />
                      </div>

                      {/* Event content */}
                      <Card className="flex-1">
                        <CardContent className="flex items-start gap-3 p-3">
                          <div
                            className={cn(
                              'flex h-8 w-8 items-center justify-center rounded-lg',
                              getEventColor(event.type) + '/10'
                            )}
                          >
                            {eventTypeIcons[event.type]}
                          </div>

                          <div className="flex-1">
                            <div className="flex items-center gap-2">
                              {event.agent && (
                                <span className="text-sm">
                                  {getAgentIcon(event.agent)}
                                </span>
                              )}
                              <span className="font-medium">{event.message}</span>
                            </div>
                            <div className="mt-1 flex items-center gap-2 text-xs text-muted-foreground">
                              {event.agent && (
                                <span>{getAgentDisplayName(event.agent)}</span>
                              )}
                              <span>•</span>
                              <span>{formatTime(event.timestamp)}</span>
                            </div>
                          </div>

                          <Badge variant="outline" className="text-xs">
                            {event.type.replace('_', ' ')}
                          </Badge>
                        </CardContent>
                      </Card>
                    </div>
                  ))
                )}
              </div>
            </div>
          </ScrollArea>
        </CardContent>
      </Card>

      {/* Event Type Legend */}
      <Card>
        <CardContent className="flex flex-wrap items-center gap-4 p-4">
          {Object.entries(eventTypeIcons).map(([type, icon]) => (
            <div key={type} className="flex items-center gap-2">
              <div
                className={cn(
                  'flex h-6 w-6 items-center justify-center rounded',
                  eventTypeColors[type as TimelineEventType] + '/10'
                )}
              >
                <span className="scale-75">{icon}</span>
              </div>
              <span className="text-xs capitalize">{type.replace('_', ' ')}</span>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

export default ResearchTimeline;