import { useQuery } from '@tanstack/react-query'
import { Loader2, History } from 'lucide-react'
import { auditApi } from '@/lib/audit-api'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'

const actionColors: Record<string, 'default' | 'destructive' | 'success' | 'secondary'> = {
  'product.created': 'success',
  'product.updated': 'default',
  'product.deleted': 'destructive',
  'product.bulk_import': 'default',
  'member.invited': 'success',
  'member.role_changed': 'default',
  'classification.created': 'secondary',
  'webhook.created': 'success',
  'webhook.deleted': 'destructive',
}

export function AuditLogPage() {
  const { data, isLoading } = useQuery({ queryKey: ['audit-log'], queryFn: () => auditApi.list(100, 0) })

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Audit log</h1>
        <p className="text-sm text-muted-foreground">
          {data?.count ?? 0} recorded actions in your organization. Append-only — nothing here can be edited or deleted.
        </p>
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : data && data.results.length > 0 ? (
        <div className="rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Action</TableHead>
                <TableHead>By</TableHead>
                <TableHead>Resource</TableHead>
                <TableHead>Details</TableHead>
                <TableHead className="text-right">When</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.results.map((entry) => (
                <TableRow key={entry.id}>
                  <TableCell>
                    <Badge variant={actionColors[entry.action] ?? 'outline'} className="font-mono text-xs">
                      {entry.action}
                    </Badge>
                  </TableCell>
                  <TableCell className="text-sm text-muted-foreground">{entry.user_email ?? '—'}</TableCell>
                  <TableCell className="text-sm">
                    {entry.resource_type}
                    {entry.resource_id && <span className="text-muted-foreground"> #{entry.resource_id}</span>}
                  </TableCell>
                  <TableCell className="max-w-xs truncate text-xs text-muted-foreground">
                    {entry.details ? JSON.stringify(entry.details) : '—'}
                  </TableCell>
                  <TableCell className="text-right text-xs text-muted-foreground">
                    {new Date(entry.created_at).toLocaleString()}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-16 text-center">
          <History className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No activity recorded yet.</p>
        </div>
      )}
    </div>
  )
}
