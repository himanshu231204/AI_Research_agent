'use client';

import { useState, useEffect } from 'react';
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Input } from '@/components/ui/input';
import { Button } from '@/components/ui/button';
import { ScrollArea } from '@/components/ui/scroll-area';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { memoryApi } from '@/services/api';
import { cn, formatTime } from '@/lib/utils';
import type { MemoryEntry, MemoryType } from '@/types';
import {
  Brain,
  Search,
  Database,
  Clock,
  Trash2,
  RefreshCw,
  ChevronDown,
  ChevronRight,
  Sparkles,
} from 'lucide-react';

export function MemoryInspector() {
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedType, setSelectedType] = useState<MemoryType | 'all'>('all');
  const [entries, setEntries] = useState<MemoryEntry[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [expandedEntry, setExpandedEntry] = useState<string | null>(null);
  const [stats, setStats] = useState({
    episodic_entries: 0,
    semantic_entries: 0,
    total_entries: 0,
  });

  useEffect(() => {
    loadStats();
  }, []);

  const loadStats = async () => {
    try {
      const data = await memoryApi.getStats();
      setStats(data);
    } catch (error) {
      console.error('Failed to load memory stats:', error);
    }
  };

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setIsLoading(true);
    try {
      const results = await memoryApi.search(searchQuery, undefined, 20);
      setEntries(results.entries);
    } catch (error) {
      console.error('Memory search failed:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const filteredEntries = selectedType === 'all'
    ? entries
    : entries.filter((e) => e.type === selectedType);

  const getTypeBadge = (type: MemoryType) => {
    const colors: Record<MemoryType, string> = {
      semantic: 'bg-purple-500',
      episodic: 'bg-blue-500',
      working: 'bg-yellow-500',
      compressed: 'bg-green-500',
    };
    return colors[type] || 'bg-gray-500';
  };

  return (
    <div className="flex h-full flex-col gap-4 p-4">
      <div className="flex items-center justify-between">
        <h2 className="text-lg font-semibold">Memory Inspector</h2>
        <Button variant="outline" size="sm" onClick={loadStats}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-3 gap-4">
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-blue-500/10 p-2">
              <Clock className="h-4 w-4 text-blue-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.episodic_entries}</p>
              <p className="text-xs text-muted-foreground">Episodic</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-purple-500/10 p-2">
              <Brain className="h-4 w-4 text-purple-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.semantic_entries}</p>
              <p className="text-xs text-muted-foreground">Semantic</p>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="flex items-center gap-3 p-4">
            <div className="rounded-full bg-green-500/10 p-2">
              <Database className="h-4 w-4 text-green-500" />
            </div>
            <div>
              <p className="text-2xl font-bold">{stats.total_entries}</p>
              <p className="text-xs text-muted-foreground">Total</p>
            </div>
          </CardContent>
        </Card>
      </div>

      {/* Search */}
      <Card>
        <CardContent className="p-4">
          <div className="flex gap-2">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
              <Input
                placeholder="Search memory..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
                className="pl-9"
              />
            </div>
            <Button onClick={handleSearch} disabled={isLoading}>
              {isLoading ? (
                <RefreshCw className="h-4 w-4 animate-spin" />
              ) : (
                'Search'
              )}
            </Button>
          </div>
        </CardContent>
      </Card>

      {/* Type Filter */}
      <div className="flex gap-2">
        {(['all', 'semantic', 'episodic', 'working', 'compressed'] as const).map((type) => (
          <Button
            key={type}
            variant={selectedType === type ? 'default' : 'outline'}
            size="sm"
            onClick={() => setSelectedType(type)}
          >
            {type === 'all' ? 'All' : type.charAt(0).toUpperCase() + type.slice(1)}
          </Button>
        ))}
      </div>

      {/* Memory Entries */}
      <Card className="flex-1">
        <CardContent className="p-0">
          <ScrollArea className="h-[400px] p-4">
            {filteredEntries.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-12 text-center">
                <Brain className="mb-2 h-8 w-8 text-muted-foreground" />
                <p className="text-sm text-muted-foreground">
                  {searchQuery ? 'No matching memories found' : 'Search to explore memory'}
                </p>
              </div>
            ) : (
              <div className="space-y-2">
                {filteredEntries.map((entry) => (
                  <div
                    key={entry.id}
                    className={cn(
                      'rounded-lg border p-3 transition-colors',
                      expandedEntry === entry.id && 'bg-muted'
                    )}
                  >
                    <div
                      className="flex cursor-pointer items-center gap-3"
                      onClick={() => setExpandedEntry(expandedEntry === entry.id ? null : entry.id)}
                    >
                      {expandedEntry === entry.id ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4" />
                      )}
                      
                      <div className={cn('h-2 w-2 rounded-full', getTypeBadge(entry.type))} />
                      
                      <span className="flex-1 truncate text-sm">{entry.content}</span>
                      
                      {entry.similarity && (
                        <Badge variant="outline" className="text-xs">
                          {Math.round(entry.similarity * 100)}% match
                        </Badge>
                      )}
                      
                      <span className="text-xs text-muted-foreground">
                        {formatTime(entry.timestamp)}
                      </span>
                    </div>

                    {expandedEntry === entry.id && (
                      <div className="mt-3 pl-7">
                        <div className="rounded bg-muted/50 p-3">
                          <p className="text-sm">{entry.content}</p>
                          {entry.metadata && (
                            <div className="mt-2 flex flex-wrap gap-2">
                              {Object.entries(entry.metadata).map(([key, value]) => (
                                <Badge key={key} variant="outline" className="text-xs">
                                  {key}: {String(value)}
                                </Badge>
                              ))}
                            </div>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </ScrollArea>
        </CardContent>
      </Card>
    </div>
  );
}

export default MemoryInspector;