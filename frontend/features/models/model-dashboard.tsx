'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Progress } from '@/components/ui/progress';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { modelsApi } from '@/services/api';
import { cn, formatNumber, formatPercentage, formatCurrency } from '@/lib/utils';
import type { ModelProvider, GPUStatus, ModelTelemetry } from '@/types';
import {
  Cpu,
  Zap,
  Brain,
  Clock,
  DollarSign,
  Activity,
  Server,
  Gauge,
  AlertTriangle,
  CheckCircle,
  XCircle,
  RefreshCw,
  ArrowRight,
  CpuIcon,
  Flame,
} from 'lucide-react';

export function ModelDashboard() {
  const [providers, setProviders] = useState<ModelProvider[]>([]);
  const [gpuStatus, setGpuStatus] = useState<GPUStatus | null>(null);
  const [telemetry, setTelemetry] = useState<ModelTelemetry | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    loadData();
    const interval = setInterval(loadData, 10000);
    return () => clearInterval(interval);
  }, []);

  const loadData = async () => {
    setIsLoading(true);
    setError(null);
    try {
      const [statusData, telemetryData] = await Promise.all([
        modelsApi.getStatus(),
        modelsApi.getTelemetry(),
      ]);
      setProviders(statusData.providers);
      setGpuStatus(statusData.gpu_status);
      setTelemetry(telemetryData);
    } catch (err) {
      console.error('Failed to load model data:', err);
      setError(err instanceof Error ? err.message : 'Failed to load model status');
    } finally {
      setIsLoading(false);
    }
  };

  const getStatusIcon = (available: boolean, status: string) => {
    if (!available) return <XCircle className="h-4 w-4 text-red-500" />;
    if (status === 'degraded') return <AlertTriangle className="h-4 w-4 text-yellow-500" />;
    return <CheckCircle className="h-4 w-4 text-green-500" />;
  };

  // Render GPU status with proper CPU/GPU handling
  const renderGPUStatus = () => {
    if (!gpuStatus) {
      return <p className="text-sm text-muted-foreground">Loading GPU status...</p>;
    }

    // Handle error state
    if (gpuStatus.status === 'error' || gpuStatus.error) {
      return (
        <div className="flex items-center gap-2">
          <XCircle className="h-4 w-4 text-red-500" />
          <span className="text-sm text-muted-foreground">
            {gpuStatus.error || 'Error checking GPU status'}
          </span>
        </div>
      );
    }

    // CPU Mode - Ollama is healthy but no GPU available
    if (gpuStatus.mode === 'cpu' || gpuStatus.status === 'cpu_mode') {
      return (
        <div className="flex items-center gap-6">
          <div className="flex items-center gap-2">
            <CpuIcon className="h-5 w-5 text-blue-500" />
            <span className="text-sm font-medium text-blue-500">CPU Inference Mode</span>
          </div>
          <Badge variant="secondary" className="bg-blue-500/20 text-blue-500">
            Ollama Active
          </Badge>
          {gpuStatus.model_loaded && (
            <div className="flex items-center gap-2">
              <Brain className="h-4 w-4 text-muted-foreground" />
              <span className="text-sm">{gpuStatus.model_loaded}</span>
            </div>
          )}
        </div>
      );
    }

    // GPU Available states
    const getGPUIndicator = () => {
      if (gpuStatus.status === 'saturated') {
        return (
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-red-500 animate-pulse" />
            <span className="text-sm font-medium text-red-500">GPU Saturated</span>
          </div>
        );
      }
      if (gpuStatus.status === 'busy') {
        return (
          <div className="flex items-center gap-2">
            <div className="h-3 w-3 rounded-full bg-yellow-500" />
            <span className="text-sm font-medium text-yellow-500">GPU Busy</span>
          </div>
        );
      }
      return (
        <div className="flex items-center gap-2">
          <div className="h-3 w-3 rounded-full bg-green-500" />
          <span className="text-sm font-medium text-green-500">GPU Available</span>
        </div>
      );
    };

    const memoryPercent = gpuStatus.memory?.percent ?? gpuStatus.memory_percent ?? 0;

    return (
      <div className="flex items-center gap-6">
        {getGPUIndicator()}

        <div className="flex-1">
          <div className="flex items-center justify-between text-sm">
            <span>Memory Usage</span>
            <span>{formatPercentage(memoryPercent)}</span>
          </div>
          <Progress
            value={memoryPercent}
            className="mt-1"
            indicatorClassName={memoryPercent > 90 ? 'bg-red-500' : memoryPercent > 70 ? 'bg-yellow-500' : 'bg-green-500'}
          />
        </div>

        {gpuStatus.gpu_count && gpuStatus.gpu_count > 0 && (
          <Badge variant="outline" className="flex items-center gap-1">
            <Zap className="h-3 w-3" />
            {gpuStatus.gpu_count} GPU{gpuStatus.gpu_count > 1 ? 's' : ''}
          </Badge>
        )}

        {gpuStatus.model_loaded && (
          <div className="flex items-center gap-2">
            <Brain className="h-4 w-4 text-muted-foreground" />
            <span className="text-sm">{gpuStatus.model_loaded}</span>
          </div>
        )}

        {gpuStatus.temperature && (
          <div className="flex items-center gap-1 text-sm">
            <Flame className="h-3 w-3 text-muted-foreground" />
            <span>{gpuStatus.temperature}°C</span>
          </div>
        )}

        <Badge
          variant={gpuStatus.status === 'saturated' ? 'destructive' : 'secondary'}
          className={cn(
            gpuStatus.status === 'available' && 'bg-green-500/20 text-green-500'
          )}
        >
          {gpuStatus.status}
        </Badge>
      </div>
    );
  };

  const localProviders = providers.filter((p) => p.type === 'local');
  const cloudProviders = providers.filter((p) => p.type === 'cloud');

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Model Routing</h2>
        <Button variant="outline" size="sm" onClick={loadData} disabled={isLoading}>
          <RefreshCw className={cn('h-4 w-4', isLoading && 'animate-spin')} />
        </Button>
      </div>

      {/* GPU Status */}
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Zap className="h-4 w-4" />
            GPU Status
          </CardTitle>
        </CardHeader>
        <CardContent>
          {error ? (
            <div className="flex items-center gap-2 text-red-500">
              <AlertTriangle className="h-4 w-4" />
              <span className="text-sm">{error}</span>
            </div>
          ) : (
            renderGPUStatus()
          )}
        </CardContent>
      </Card>

      {/* Ollama Provider Detail Card */}
      {localProviders.length > 0 && localProviders[0] && (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-base">
              <Server className="h-4 w-4" />
              Ollama Provider
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-4 gap-4">
              <div className="flex items-center gap-2">
                {getStatusIcon(localProviders[0].available, localProviders[0].status)}
                <div>
                  <p className="text-sm font-medium">{localProviders[0].status}</p>
                  <p className="text-xs text-muted-foreground">Provider Status</p>
                </div>
              </div>

              {localProviders[0].latency_ms > 0 && (
                <div className="flex items-center gap-2">
                  <Clock className="h-4 w-4 text-muted-foreground" />
                  <div>
                    <p className="text-sm font-medium">{localProviders[0].latency_ms}ms</p>
                    <p className="text-xs text-muted-foreground">Latency</p>
                  </div>
                </div>
              )}

              <div className="flex items-center gap-2">
                <Brain className="h-4 w-4 text-muted-foreground" />
                <div>
                  <p className="text-sm font-medium">{localProviders[0].models.length}</p>
                  <p className="text-xs text-muted-foreground">Models</p>
                </div>
              </div>

              <div className="flex items-center gap-2">
                {localProviders[0].inference_mode === 'cpu' ? (
                  <CpuIcon className="h-4 w-4 text-blue-500" />
                ) : (
                  <Zap className="h-4 w-4 text-green-500" />
                )}
                <div>
                  <p className="text-sm font-medium capitalize">
                    {localProviders[0].inference_mode || 'unknown'}
                  </p>
                  <p className="text-xs text-muted-foreground">Mode</p>
                </div>
              </div>
            </div>

            {localProviders[0].model_loaded && (
              <div className="mt-4 flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Loaded Model:</span>
                <Badge variant="outline">{localProviders[0].model_loaded}</Badge>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      <Tabs defaultValue="providers" className="flex-1">
        <TabsList>
          <TabsTrigger value="providers">Providers</TabsTrigger>
          <TabsTrigger value="telemetry">Telemetry</TabsTrigger>
          <TabsTrigger value="routing">Routing</TabsTrigger>
        </TabsList>

        <TabsContent value="providers" className="space-y-4">
          {/* Local Providers */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Server className="h-4 w-4" />
                Local Models (Ollama)
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {localProviders.map((provider) => (
                  <div
                    key={provider.name}
                    className="flex items-center gap-4 rounded-lg border p-3"
                  >
                    {getStatusIcon(provider.available, provider.status)}

                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <p className="font-medium">{provider.name}</p>
                        {provider.inference_mode && (
                          <Badge variant="outline" className="text-xs">
                            {provider.inference_mode}
                          </Badge>
                        )}
                      </div>
                      <p className="text-xs text-muted-foreground">
                        {provider.models.join(', ') || 'No models loaded'}
                      </p>
                    </div>

                    <div className="flex items-center gap-4 text-sm">
                      {provider.latency_ms > 0 && (
                        <div className="flex items-center gap-1">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          <span>{provider.latency_ms}ms</span>
                        </div>
                      )}
                      <Badge variant={provider.available ? 'success' : 'destructive'}>
                        {provider.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* Cloud Providers */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 text-sm">
                <Cloud className="h-4 w-4" />
                Cloud Providers
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {cloudProviders.map((provider) => (
                  <div
                    key={provider.name}
                    className="flex items-center gap-4 rounded-lg border p-3"
                  >
                    {getStatusIcon(provider.available, provider.status)}

                    <div className="flex-1">
                      <p className="font-medium">{provider.name}</p>
                      <p className="text-xs text-muted-foreground">
                        {provider.models.slice(0, 5).join(', ')}
                        {provider.models.length > 5 && ` +${provider.models.length - 5} more`}
                      </p>
                    </div>

                    <div className="flex items-center gap-4 text-sm">
                      {provider.latency_ms > 0 && (
                        <div className="flex items-center gap-1">
                          <Clock className="h-3 w-3 text-muted-foreground" />
                          <span>{provider.latency_ms}ms</span>
                        </div>
                      )}
                      <Badge variant={provider.available ? 'success' : 'destructive'}>
                        {provider.status}
                      </Badge>
                    </div>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="telemetry">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Telemetry Summary</CardTitle>
            </CardHeader>
            <CardContent>
              {telemetry ? (
                <div className="grid grid-cols-4 gap-4">
                  <div className="rounded-lg bg-muted p-4">
                    <p className="text-2xl font-bold">{formatNumber(telemetry.summary.total_requests)}</p>
                    <p className="text-xs text-muted-foreground">Total Requests</p>
                  </div>
                  <div className="rounded-lg bg-muted p-4">
                    <p className="text-2xl font-bold">{formatNumber(telemetry.summary.total_tokens)}</p>
                    <p className="text-xs text-muted-foreground">Total Tokens</p>
                  </div>
                  <div className="rounded-lg bg-muted p-4">
                    <p className="text-2xl font-bold">{formatCurrency(telemetry.summary.total_cost_usd)}</p>
                    <p className="text-xs text-muted-foreground">Total Cost</p>
                  </div>
                  <div className="rounded-lg bg-muted p-4">
                    <p className="text-2xl font-bold">{Math.round(telemetry.summary.avg_latency_ms)}ms</p>
                    <p className="text-xs text-muted-foreground">Avg Latency</p>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground">Loading telemetry...</p>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="routing">
          <Card>
            <CardHeader>
              <CardTitle className="text-base">Model Routing Chain</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                {[
                  { task: 'Planning', primary: 'qwen3 (local)', fallback: 'GPT-5 (cloud)' },
                  { task: 'Coding', primary: 'deepseek-coder (local)', fallback: 'Claude (cloud)' },
                  { task: 'Reflection', primary: 'mistral (local)', fallback: 'Gemini (cloud)' },
                  { task: 'Summarization', primary: 'llama3 (local)', fallback: 'Claude (cloud)' },
                ].map((route) => (
                  <div
                    key={route.task}
                    className="flex items-center gap-4 rounded-lg border p-3"
                  >
                    <span className="font-medium">{route.task}</span>
                    <ArrowRight className="h-4 w-4 text-muted-foreground" />
                    <Badge variant="outline">{route.primary}</Badge>
                    <span className="text-xs text-muted-foreground">→</span>
                    <Badge variant="secondary">{route.fallback}</Badge>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  );
}

// Simple Cloud icon component
function Cloud({ className }: { className?: string }) {
  return (
    <svg
      className={className}
      xmlns="http://www.w3.org/2000/svg"
      width="24"
      height="24"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="2"
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M17.5 19c0-3.037-2.463-5.5-5.5-5.5S6.5 15.963 6.5 19" />
      <path d="M20.4 14.5c1-1.2 1.6-2.8 1.6-4.5 0-4.4-3.6-8-8-8s-8 3.6-8 8c0 .7.1 1.4.3 2" />
    </svg>
  );
}

export default ModelDashboard;