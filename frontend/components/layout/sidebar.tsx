'use client';

import { useState } from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import { cn } from '@/lib/utils';
import { useUIStore } from '@/stores';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Badge } from '@/components/ui/badge';
import {
  MessageSquare,
  Workflow,
  Users,
  Brain,
  ListOrdered,
  Cpu,
  BarChart3,
  FileText,
  Settings,
  ChevronLeft,
  ChevronRight,
  Sparkles,
  Activity,
} from 'lucide-react';

const navItems = [
  { id: 'chat', label: 'Chat', icon: MessageSquare, href: '/' },
  { id: 'workflow', label: 'Workflow', icon: Workflow, href: '/workflow' },
  { id: 'agents', label: 'Agents', icon: Users, href: '/agents' },
  { id: 'memory', label: 'Memory', icon: Brain, href: '/memory' },
  { id: 'queue', label: 'Queue', icon: ListOrdered, href: '/queue' },
  { id: 'models', label: 'Models', icon: Cpu, href: '/models' },
  { id: 'observability', label: 'Observability', icon: BarChart3, href: '/observability' },
  { id: 'artifacts', label: 'Artifacts', icon: FileText, href: '/artifacts' },
];

export function Sidebar() {
  const pathname = usePathname();
  const { sidebarOpen, toggleSidebar, activePanel, setActivePanel } = useUIStore();
  const [isHovered, setIsHovered] = useState<string | null>(null);

  return (
    <aside
      className={cn(
        'fixed left-0 top-0 z-40 h-screen border-r bg-card transition-all duration-300',
        sidebarOpen ? 'w-64' : 'w-16'
      )}
    >
      <div className="flex h-16 items-center border-b px-4">
        <Link href="/" className="flex items-center gap-2">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-primary">
            <Sparkles className="h-5 w-5 text-primary-foreground" />
          </div>
          {sidebarOpen && (
            <span className="font-semibold">AI Research Agent</span>
          )}
        </Link>
      </div>

      <ScrollArea className="h-[calc(100vh-4rem)]">
        <nav className="flex flex-col gap-1 p-2">
          {navItems.map((item) => {
            const isActive = pathname === item.href || activePanel === item.id;
            const Icon = item.icon;

            return (
              <Link
                key={item.id}
                href={item.href}
                onClick={() => setActivePanel(item.id as any)}
                className={cn(
                  'flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors',
                  isActive
                    ? 'bg-primary/10 text-primary'
                    : 'text-muted-foreground hover:bg-muted hover:text-foreground',
                  !sidebarOpen && 'justify-center px-2'
                )}
                onMouseEnter={() => setIsHovered(item.id)}
                onMouseLeave={() => setIsHovered(null)}
              >
                <Icon className={cn('h-5 w-5 flex-shrink-0', isActive && 'text-primary')} />
                {sidebarOpen && <span>{item.label}</span>}
                
                {!sidebarOpen && isHovered && (
                  <div className="absolute left-14 z-50 rounded-md bg-popover px-2 py-1 text-sm shadow-md">
                    {item.label}
                  </div>
                )}
              </Link>
            );
          })}
        </nav>

        {sidebarOpen && (
          <div className="border-t p-4">
            <div className="flex items-center gap-2 rounded-md bg-muted/50 p-3">
              <Activity className="h-4 w-4 text-green-500" />
              <div className="flex-1">
                <p className="text-xs font-medium">System Status</p>
                <p className="text-xs text-muted-foreground">All systems operational</p>
              </div>
              <Badge variant="success" className="text-[10px]">Online</Badge>
            </div>
          </div>
        )}
      </ScrollArea>

      <Button
        variant="ghost"
        size="icon"
        className="absolute -right-3 top-20 h-6 w-6 rounded-full border bg-background shadow-md"
        onClick={toggleSidebar}
      >
        {sidebarOpen ? (
          <ChevronLeft className="h-3 w-3" />
        ) : (
          <ChevronRight className="h-3 w-3" />
        )}
      </Button>
    </aside>
  );
}

export default Sidebar;