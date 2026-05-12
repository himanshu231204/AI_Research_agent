/**
 * Frontend API and State Tests for GPU Detection
 */

import { describe, it, expect, vi, beforeEach } from 'vitest';
import { renderHook, act, waitFor } from '@testing-library/react';
import React from 'react';

// Mock GPU Status types
interface MockGPUStatus {
  available: boolean;
  mode?: 'nvidia' | 'amd' | 'cpu' | 'unknown';
  status?: 'available' | 'busy' | 'saturated' | 'unavailable' | 'cpu_mode' | 'error';
  gpu_count?: number;
  memory?: {
    total_mb: number;
    used_mb: number;
    free_mb: number;
    percent: number;
  };
  display_status?: string;
  display_icon?: string;
  error?: string;
}

describe('GPU Status Types', () => {
  it('should support CPU mode status', () => {
    const status: MockGPUStatus = {
      available: false,
      mode: 'cpu',
      status: 'cpu_mode',
      display_status: 'CPU Inference Mode',
      display_icon: 'cpu',
    };

    expect(status.mode).toBe('cpu');
    expect(status.status).toBe('cpu_mode');
    expect(status.display_status).toBe('CPU Inference Mode');
  });

  it('should support GPU available status', () => {
    const status: MockGPUStatus = {
      available: true,
      mode: 'nvidia',
      status: 'available',
      gpu_count: 1,
      memory: {
        total_mb: 24576,
        used_mb: 8192,
        free_mb: 16384,
        percent: 33.3,
      },
      display_status: 'GPU Available',
      display_icon: 'available',
    };

    expect(status.available).toBe(true);
    expect(status.mode).toBe('nvidia');
    expect(status.memory?.percent).toBe(33.3);
  });

  it('should support GPU saturated status', () => {
    const status: MockGPUStatus = {
      available: true,
      mode: 'nvidia',
      status: 'saturated',
      gpu_count: 1,
      memory: {
        total_mb: 24576,
        used_mb: 23500,
        free_mb: 1076,
        percent: 95.7,
      },
      display_status: 'GPU Saturated',
      display_icon: 'busy',
    };

    expect(status.status).toBe('saturated');
    expect(status.memory?.percent).toBe(95.7);
  });

  it('should support error status', () => {
    const status: MockGPUStatus = {
      available: false,
      mode: 'unknown',
      status: 'error',
      error: 'Failed to connect to Ollama',
      display_status: 'GPU Status Error',
      display_icon: 'error',
    };

    expect(status.status).toBe('error');
    expect(status.error).toBe('Failed to connect to Ollama');
  });
});

describe('GPU Status Display Logic', () => {
  const getDisplayText = (status: MockGPUStatus): string => {
    if (status.status === 'error' || status.error) {
      return status.error || 'Error checking GPU status';
    }

    if (status.mode === 'cpu' || status.status === 'cpu_mode') {
      return 'CPU Inference Mode';
    }

    if (status.mode === 'nvidia') {
      if (status.status === 'saturated') {
        return `GPU Saturated (${status.memory?.percent?.toFixed(0)}%)`;
      }
      if (status.status === 'busy') {
        return `GPU Busy (${status.memory?.percent?.toFixed(0)}%)`;
      }
      return 'GPU Available';
    }

    return 'GPU Status Unknown';
  };

  it('should display CPU mode correctly', () => {
    const status: MockGPUStatus = {
      available: false,
      mode: 'cpu',
      status: 'cpu_mode',
    };

    expect(getDisplayText(status)).toBe('CPU Inference Mode');
  });

  it('should display GPU saturated correctly', () => {
    const status: MockGPUStatus = {
      available: true,
      mode: 'nvidia',
      status: 'saturated',
      memory: { total_mb: 24576, used_mb: 23500, free_mb: 1076, percent: 95.7 },
    };

    expect(getDisplayText(status)).toBe('GPU Saturated (96%)');
  });

  it('should display GPU busy correctly', () => {
    const status: MockGPUStatus = {
      available: true,
      mode: 'nvidia',
      status: 'busy',
      memory: { total_mb: 24576, used_mb: 18000, free_mb: 6576, percent: 73.3 },
    };

    expect(getDisplayText(status)).toBe('GPU Busy (73%)');
  });

  it('should display GPU available correctly', () => {
    const status: MockGPUStatus = {
      available: true,
      mode: 'nvidia',
      status: 'available',
      memory: { total_mb: 24576, used_mb: 8192, free_mb: 16384, percent: 33.3 },
    };

    expect(getDisplayText(status)).toBe('GPU Available');
  });

  it('should display error correctly', () => {
    const status: MockGPUStatus = {
      available: false,
      status: 'error',
      error: 'Connection timeout',
    };

    expect(getDisplayText(status)).toBe('Connection timeout');
  });
});

describe('API Response Handling', () => {
  interface ModelStatusResponse {
    timestamp: string;
    providers: Array<{
      name: string;
      type: string;
      status: string;
      available: boolean;
      models: string[];
      latency_ms: number;
      inference_mode?: string;
      gpu_count?: number;
      gpu_available?: boolean;
    }>;
    gpu_status: MockGPUStatus;
    model_health: Record<string, unknown>;
  }

  it('should parse CPU mode response correctly', () => {
    const response: ModelStatusResponse = {
      timestamp: new Date().toISOString(),
      providers: [
        {
          name: 'ollama',
          type: 'local',
          status: 'healthy',
          available: true,
          models: ['qwen3', 'llama3'],
          latency_ms: 150,
          inference_mode: 'cpu',
          gpu_available: false,
        },
      ],
      gpu_status: {
        available: false,
        mode: 'cpu',
        status: 'cpu_mode',
        display_status: 'CPU Inference Mode',
        display_icon: 'cpu',
      },
      model_health: {},
    };

    expect(response.providers[0].inference_mode).toBe('cpu');
    expect(response.gpu_status.mode).toBe('cpu');
    expect(response.gpu_status.display_status).toBe('CPU Inference Mode');
  });

  it('should parse GPU available response correctly', () => {
    const response: ModelStatusResponse = {
      timestamp: new Date().toISOString(),
      providers: [
        {
          name: 'ollama',
          type: 'local',
          status: 'healthy',
          available: true,
          models: ['qwen3'],
          latency_ms: 50,
          inference_mode: 'nvidia',
          gpu_count: 1,
          gpu_available: true,
        },
      ],
      gpu_status: {
        available: true,
        mode: 'nvidia',
        status: 'available',
        gpu_count: 1,
        memory: {
          total_mb: 24576,
          used_mb: 8192,
          free_mb: 16384,
          percent: 33.3,
        },
        compute_utilization: 35,
        temperature: 65,
        driver_version: '525.85.05',
        model_loaded: 'qwen3',
        display_status: 'GPU Available',
        display_icon: 'available',
      },
      model_health: {},
    };

    expect(response.gpu_status.available).toBe(true);
    expect(response.gpu_status.mode).toBe('nvidia');
    expect(response.gpu_status.gpu_count).toBe(1);
    expect(response.gpu_status.memory?.percent).toBe(33.3);
  });
});

describe('Memory Formatting', () => {
  const formatMemory = (mb: number): string => {
    if (mb >= 1024) {
      return `${(mb / 1024).toFixed(1)} GB`;
    }
    return `${mb.toFixed(0)} MB`;
  };

  const formatPercentage = (percent: number): string => {
    return `${percent.toFixed(1)}%`;
  };

  it('should format memory in GB correctly', () => {
    expect(formatMemory(8192)).toBe('8.0 GB');
    expect(formatMemory(24576)).toBe('24.0 GB');
  });

  it('should format memory in MB correctly for small values', () => {
    expect(formatMemory(512)).toBe('512 MB');
  });

  it('should format percentage correctly', () => {
    expect(formatPercentage(33.333)).toBe('33.3%');
    expect(formatPercentage(95.7)).toBe('95.7%');
  });
});
