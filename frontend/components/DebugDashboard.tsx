/**
 * Frontend Debug Dashboard Component.
 *
 * Provides real-time diagnostics for API connectivity, WebSocket status,
 * and backend health monitoring.
 */

'use client';

import { useEffect, useState } from 'react';
import { healthApi, researchApi, modelsApi } from '@/services/api';
import { wsService } from '@/websocket';
import { useWSStore } from '@/stores';

interface DebugInfo {
  apiStatus: 'checking' | 'connected' | 'disconnected' | 'error';
  wsStatus: 'connecting' | 'connected' | 'disconnected' | 'error';
  lastApiLatency: number | null;
  lastWsMessage: object | null;
  activeSessions: string[];
  registeredRoutes: string[];
  backendServices: Record<string, { status: string; latency_ms?: number }>;
  failedRequests: Array<{ url: string; error: string; timestamp: string }>;
}

interface HealthCheck {
  status: string;
  services: Record<string, { status: string; latency_ms?: number; error?: string }>;
}

export function DebugDashboard() {
  const [debugInfo, setDebugInfo] = useState<DebugInfo>({
    apiStatus: 'checking',
    wsStatus: 'disconnected',
    lastApiLatency: null,
    lastWsMessage: null,
    activeSessions: [],
    registeredRoutes: [],
    backendServices: {},
    failedRequests: [],
  });

  const wsStore = useWSStore();
  const [isExpanded, setIsExpanded] = useState(false);

  // Check API health
  useEffect(() => {
    const checkApiHealth = async () => {
      const startTime = performance.now();
      try {
        const health = await healthApi.check();
        const latency = performance.now() - startTime;
        
        setDebugInfo(prev => ({
          ...prev,
          apiStatus: health.status === 'healthy' ? 'connected' : 'disconnected',
          lastApiLatency: Math.round(latency),
        }));

        // Get detailed health info
        try {
          const ready = await healthApi.ready();
          setDebugInfo(prev => ({
            ...prev,
            backendServices: ready.services as Record<string, { status: string; latency_ms?: number }>,
          }));
        } catch {
          // Ignore detailed health errors
        }

        // Get route info
        try {
          const routeResponse = await fetch(`${process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}/health/routes`);
          const routeData = await routeResponse.json();
          setDebugInfo(prev => ({
            ...prev,
            registeredRoutes: routeData.routes?.map((r: { path: string }) => r.path) || [],
          }));
        } catch {
          // Ignore route errors
        }
      } catch (error) {
        setDebugInfo(prev => ({
          ...prev,
          apiStatus: 'error',
          failedRequests: [
            ...prev.failedRequests,
            {
              url: '/health',
              error: error instanceof Error ? error.message : 'Unknown error',
              timestamp: new Date().toISOString(),
            },
          ],
        }));
      }
    };

    checkApiHealth();
    const interval = setInterval(checkApiHealth, 10000);
    return () => clearInterval(interval);
  }, []);

  // Check WebSocket status
  useEffect(() => {
    setDebugInfo(prev => ({
      ...prev,
      wsStatus: wsStore.isConnected ? 'connected' : 'disconnected',
      lastWsMessage: (wsStore.lastMessage as object) ?? null,
    }));
  }, [wsStore.isConnected, wsStore.lastMessage]);

  // Get active sessions from websocket manager
  useEffect(() => {
    const sessions = wsService.currentSessionId ? [wsService.currentSessionId] : [];
    setDebugInfo(prev => ({ ...prev, activeSessions: sessions }));
  }, []);

  if (!isExpanded) {
    return (
      <button
        onClick={() => setIsExpanded(true)}
        className="fixed bottom-4 right-4 bg-gray-800 text-white px-4 py-2 rounded-lg shadow-lg text-sm hover:bg-gray-700"
        style={{ zIndex: 9999 }}
      >
        🐛 Debug ({debugInfo.apiStatus === 'connected' ? '✓' : '✗'} API, {debugInfo.wsStatus === 'connected' ? '✓' : '✗'} WS)
      </button>
    );
  }

  return (
    <div 
      className="fixed bottom-4 right-4 bg-gray-900 text-white p-4 rounded-lg shadow-xl text-xs max-w-md overflow-auto"
      style={{ zIndex: 9999, maxHeight: '80vh' }}
    >
      <div className="flex justify-between items-center mb-4">
        <h3 className="font-bold text-sm">🔧 API Debug Dashboard</h3>
        <button 
          onClick={() => setIsExpanded(false)}
          className="text-gray-400 hover:text-white"
        >
          ✕
        </button>
      </div>

      {/* API Status */}
      <div className="mb-4 p-3 bg-gray-800 rounded">
        <h4 className="font-bold mb-2">API Status</h4>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-400">Status:</span>
            <span className={`ml-2 ${
              debugInfo.apiStatus === 'connected' ? 'text-green-400' : 
              debugInfo.apiStatus === 'error' ? 'text-red-400' : 'text-yellow-400'
            }`}>
              {debugInfo.apiStatus}
            </span>
          </div>
          <div>
            <span className="text-gray-400">Latency:</span>
            <span className="ml-2">{debugInfo.lastApiLatency ? `${debugInfo.lastApiLatency}ms` : 'N/A'}</span>
          </div>
        </div>
      </div>

      {/* WebSocket Status */}
      <div className="mb-4 p-3 bg-gray-800 rounded">
        <h4 className="font-bold mb-2">WebSocket Status</h4>
        <div className="grid grid-cols-2 gap-2 text-xs">
          <div>
            <span className="text-gray-400">Status:</span>
            <span className={`ml-2 ${
              debugInfo.wsStatus === 'connected' ? 'text-green-400' : 
              debugInfo.wsStatus === 'error' ? 'text-red-400' : 'text-yellow-400'
            }`}>
              {debugInfo.wsStatus}
            </span>
          </div>
          <div>
            <span className="text-gray-400">Sessions:</span>
            <span className="ml-2">{debugInfo.activeSessions.length}</span>
          </div>
        </div>
        {wsStore.connectionError && (
          <div className="mt-2 text-red-400 text-xs">
            Error: {wsStore.connectionError}
          </div>
        )}
      </div>

      {/* Backend Services */}
      <div className="mb-4 p-3 bg-gray-800 rounded">
        <h4 className="font-bold mb-2">Backend Services</h4>
        <div className="space-y-1 text-xs">
          {Object.entries(debugInfo.backendServices).map(([name, info]) => (
            <div key={name} className="flex justify-between">
              <span className="text-gray-400">{name}:</span>
              <span className={info.status === 'healthy' ? 'text-green-400' : 'text-red-400'}>
                {info.status}
                {info.latency_ms ? ` (${info.latency_ms}ms)` : ''}
              </span>
            </div>
          ))}
          {Object.keys(debugInfo.backendServices).length === 0 && (
            <div className="text-gray-500">No service data available</div>
          )}
        </div>
      </div>

      {/* Registered Routes */}
      <div className="mb-4 p-3 bg-gray-800 rounded">
        <h4 className="font-bold mb-2">Registered Routes ({debugInfo.registeredRoutes.length})</h4>
        <div className="max-h-32 overflow-auto space-y-1 text-xs">
          {debugInfo.registeredRoutes.map((route) => (
            <div key={route} className="text-gray-300 truncate">{route}</div>
          ))}
          {debugInfo.registeredRoutes.length === 0 && (
            <div className="text-gray-500">No routes available</div>
          )}
        </div>
      </div>

      {/* Failed Requests */}
      <div className="p-3 bg-gray-800 rounded">
        <h4 className="font-bold mb-2">Failed Requests ({debugInfo.failedRequests.length})</h4>
        <div className="space-y-2 text-xs max-h-32 overflow-auto">
          {debugInfo.failedRequests.map((req, idx) => (
            <div key={idx} className="text-red-300">
              <div className="truncate">{req.url}</div>
              <div className="text-gray-500 text-xs">{req.error}</div>
            </div>
          ))}
          {debugInfo.failedRequests.length === 0 && (
            <div className="text-green-400">✓ No failed requests</div>
          )}
        </div>
      </div>

      {/* Last WebSocket Message */}
      {debugInfo.lastWsMessage && (
        <div className="mt-4 p-3 bg-gray-800 rounded">
          <h4 className="font-bold mb-2">Last WS Message</h4>
          <pre className="text-xs text-gray-300 overflow-auto max-h-24">
            {JSON.stringify(debugInfo.lastWsMessage, null, 2)}
          </pre>
        </div>
      )}

      {/* Environment Info */}
      <div className="mt-4 p-3 bg-gray-800 rounded">
        <h4 className="font-bold mb-2">Environment</h4>
        <div className="text-xs space-y-1">
          <div>
            <span className="text-gray-400">API URL:</span>
            <span className="ml-2">{process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000'}</span>
          </div>
          <div>
            <span className="text-gray-400">WS URL:</span>
            <span className="ml-2">{process.env.NEXT_PUBLIC_WS_URL || 'ws://localhost:8000'}</span>
          </div>
          <div>
            <span className="text-gray-400">API Prefix:</span>
            <span className="ml-2">{process.env.NEXT_PUBLIC_API_PREFIX || '/api/v1'}</span>
          </div>
        </div>
      </div>
    </div>
  );
}

export default DebugDashboard;
