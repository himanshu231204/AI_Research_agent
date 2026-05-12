'use client';

import { MemoryInspector } from '@/features/memory/memory-inspector';

export default function MemoryPage() {
  return (
    <div className="h-full">
      <MemoryInspector />
    </div>
  );
}