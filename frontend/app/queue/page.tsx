'use client';

import { QueueMonitor } from '@/features/queue/queue-monitor';

export default function QueuePage() {
  return (
    <div className="h-full">
      <QueueMonitor />
    </div>
  );
}