'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { queueApi } from '@/services/api';
import { cn, formatNumber } from '@/lib/utils';
import type { QueueInfo, WorkerInfo } from '@/types';
import {
  ListOrdered,
  Server,
  Activity,
  Clock,
  CheckCircle,
  XCircle,
  RefreshCw,
  Zap,
  AlertTriangle,
} from 'lucide-react';

export function QueueMonitor() {
  const [queues, setQueues] = useState<QueueInfo[]>([]);
  const [workers, setWorkers] = useState<WorkerInfo[]>([]);
  const [isLoading, setIsLoading] = useState(true);
  const [lastUpdate, setLastUpdate] = useState<Date>(new Date());

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 5000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    try {
      const [queueData, workerData] = await Promise.all([
        queueApi.getQueues(),
        queueApi.getWorkers(),
      ]);
      setQueues(queueData);
      setWorkers(workerData);
      setLastUpdate(new Date());
    } catch (error) {
      console.error('Failed to load queue data:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const getQueueStatus = (queue: QueueInfo) => {
    if (queue.failed_tasks > 0) return 'error';
    if (queue.depth > 10) return 'warning';
    return 'healthy';
  };

  const totalDepth = queues.reduce((sum, q) => sum + q.depth, 0);
  const totalWorkers = workers.filter((w) => w.status === 'online').length;
  const totalCompleted = queues.reduce((sum, q) => sum + q.completed_tasks, 0);
  const totalFailed = queues.reduce((sum, q) => sum + q.failed_tasks, 0);

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Queue Monitoring</h2>
        <div className="flex items-center gap-2">
          <span className="text-xs text-muted-foreground">
            Last update: {lastUpdate.toLocaleTimeString()}
          </span>
          <Button variant="outline" size="sm" onClick={loadData} disabled={isLoading}>
            <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
          </Button>
        </div>
      </div>

      {/* Summary Stats */}
      <div className="grid grid-cols-4 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-blue-500/10 p-2">
              <ListOrdered className="h-4 w-4 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalDepth}</p>
              <p className="text-xs text-muted-foreground">Total Queue Depth</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-green-500/10 p-2">
              <Server className="h-4 w-4 text-green-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{totalWorkers}</p>
              <p className="text-xs text-muted-foreground">Active Workers</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-purple-500/10 p-2">
              <CheckCircle className="h-4 w-4 text-purple-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{formatNumber(totalCompleted)}</p>
              <p className="text-xs text-muted-foreground">Completed</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-red-500/10 p-2">
              <XCircle className="h-4 w-4 text-red-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{formatNumber(totalFailed)}</p>
              <p className="text-xs text-muted-foreground">Failed</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Queue List */}
      <div className="grid grid-cols-2 gap-4">
        <Card className="col-span-2">
          <CardHeader>
            <CardTitle className="text-base">Queues</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {queues.map((queue) => (
                <div
                  key={queue.name}
                  className={cn(
                    'flex items-center gap-4 rounded-lg border p-3',
                    getQueueStatus(queue) === 'error' && 'border-red-500 bg-red-500/5',
                    getQueueStatus(queue) === 'warning' && 'border-yellow-500 bg-yellow-500/5'
                  )}
                >
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{queue.name}</span>
                      {getQueueStatus(queue) === 'error' && (
                        <AlertTriangle className="h-4 w-4 text-red-500" />
                      )}
                    </div>
                    <div className="mt-1 flex items-center gap-4 text-xs text-muted-foreground">
                      <span>{queue.active_workers} workers</span>
                      <span>{queue.completed_tasks} completed</span>
                      <span>{queue.failed_tasks} failed</span>
                    </div>
                  </div>

                  <div className="flex items-center gap-4">
                    <div className="text-right">
                      <p className="text-lg font-bold">{queue.depth}</p>
                      <p className="text-xs text-muted-foreground">pending</p>
                    </div>
                    <Badge
                      variant={getQueueStatus(queue) === 'healthy' ? 'secondary' : 'destructive'}
                    >
                      {getQueueStatus(queue)}
                    </Badge>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Workers */}
      <Card>
        <CardHeader>
          <CardTitle className="text-base">Workers</CardTitle>
        </CardHeader>
        <CardContent>
          {workers.length === 0 ? (
            <div className="flex flex-col items-center justify-center py-8 text-center">
              <Server className="mb-2 h-8 w-8 text-muted-foreground" />
              <p className="text-sm text-muted-foreground">
                No workers connected. Start Celery workers to see them here.
              </p>
            </div>
          ) : (
            <div className="grid grid-cols-3 gap-4">
              {workers.map((worker) => (
                <div
                  key={worker.id}
                  className="rounded-lg border p-3"
                >
                  <div className="flex items-center justify-between">
                    <span className="font-medium">{worker.name}</span>
                    <Badge
                      variant={worker.status === 'online' ? 'success' : 'secondary'}
                    >
                      {worker.status}
                    </Badge>
                  </div>
                  <div className="mt-2 text-xs text-muted-foreground">
                    <p>{worker.tasks_completed} completed</p>
                    <p>{worker.tasks_failed} failed</p>
                  </div>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default QueueMonitor;