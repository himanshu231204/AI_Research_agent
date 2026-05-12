'use client';

import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { useUIStore, useWSStore, useResearchStore } from '@/stores';
import {
  Search,
  Bell,
  Settings,
  Moon,
  Sun,
  Wifi,
  WifiOff,
  Loader2,
  X,
} from 'lucide-react';

interface HeaderProps {
  title?: string;
}

export function Header({ title = 'AI Research Agent' }: HeaderProps) {
  const { theme, setTheme } = useUIStore();
  const { isConnected, connectionError } = useWSStore();
  const { status, progress } = useResearchStore();
  const [showNotifications, setShowNotifications] = useState(false);

  const getStatusBadge = () => {
    switch (status) {
      case 'running':
      case 'researching':
      case 'planning':
      case 'reflecting':
      case 'writing':
        return (
          <Badge variant="warning" className="gap-1">
            <Loader2 className="h-3 w-3 animate-spin" />
            {Math.round(progress * 100)}%
          </Badge>
        );
      case 'completed':
        return <Badge variant="success">Completed</Badge>;
      case 'failed':
        return <Badge variant="destructive">Failed</Badge>;
      default:
        return <Badge variant="secondary">Idle</Badge>;
    }
  };

  return (
    <header className="sticky top-0 z-30 flex h-16 items-center justify-between border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/60">
      <div className="flex items-center gap-4">
        <h1 className="text-lg font-semibold">{title}</h1>
        {getStatusBadge()}
      </div>

      <div className="flex items-center gap-2">
        <div className="relative hidden md:block">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            placeholder="Search sessions..."
            className="w-64 pl-9"
          />
        </div>

        <div className="flex items-center gap-1 rounded-md border px-2 py-1">
          {isConnected ? (
            <>
              <Wifi className="h-4 w-4 text-green-500" />
              <span className="text-xs text-muted-foreground">Connected</span>
            </>
          ) : (
            <>
              <WifiOff className="h-4 w-4 text-red-500" />
              <span className="text-xs text-muted-foreground">
                {connectionError || 'Disconnected'}
              </span>
            </>
          )}
        </div>

        <Button
          variant="ghost"
          size="icon"
          className="relative"
          onClick={() => setShowNotifications(!showNotifications)}
        >
          <Bell className="h-5 w-5" />
          <span className="absolute right-1 top-1 h-2 w-2 rounded-full bg-destructive" />
        </Button>

        <Button
          variant="ghost"
          size="icon"
          onClick={() => setTheme(theme === 'dark' ? 'light' : 'dark')}
        >
          {theme === 'dark' ? (
            <Sun className="h-5 w-5" />
          ) : (
            <Moon className="h-5 w-5" />
          )}
        </Button>

        <Button variant="ghost" size="icon">
          <Settings className="h-5 w-5" />
        </Button>
      </div>

      {showNotifications && (
        <div className="absolute right-4 top-16 w-80 rounded-lg border bg-popover p-4 shadow-lg">
          <div className="flex items-center justify-between">
            <h3 className="font-semibold">Notifications</h3>
            <Button
              variant="ghost"
              size="icon"
              className="h-6 w-6"
              onClick={() => setShowNotifications(false)}
            >
              <X className="h-4 w-4" />
            </Button>
          </div>
          <div className="mt-4 text-center text-sm text-muted-foreground">
            No new notifications
          </div>
        </div>
      )}
    </header>
  );
}

export default Header;