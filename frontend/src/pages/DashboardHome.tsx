import { useQuery } from '@tanstack/react-query'
import { BarChart, Bar, XAxis, YAxis, ResponsiveContainer, Tooltip, Cell } from 'recharts'
import { Package, Search, CheckCircle2, TrendingUp } from 'lucide-react'
import { Link } from 'react-router-dom'
import { classifyApi } from '@/lib/classify-api'
import { productsApi } from '@/lib/products-api'
import { useAuth } from '@/lib/auth-context'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'

function StatCard({ icon: Icon, label, value, hint }: { icon: any; label: string; value: string | number; hint?: string }) {
  return (
    <Card>
      <CardContent className="flex items-center gap-4 p-5">
        <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-lg bg-primary/15 text-primary">
          <Icon className="h-5 w-5" />
        </div>
        <div>
          <p className="text-2xl font-semibold leading-none">{value}</p>
          <p className="mt-1 text-sm text-muted-foreground">{label}</p>
          {hint && <p className="text-xs text-muted-foreground/70">{hint}</p>}
        </div>
      </CardContent>
    </Card>
  )
}

export function DashboardHome() {
  const { user } = useAuth()
  const history = useQuery({ queryKey: ['classification-history-full'], queryFn: () => classifyApi.history(50) })
  const products = useQuery({ queryKey: ['products-count'], queryFn: () => productsApi.list(1, 0) })

  const results = history.data?.results ?? []
  const classifiedCount = results.filter((r) => r.is_classified).length
  const unresolvedCount = results.length - classifiedCount
  const avgConfidence =
    results.length > 0
      ? Math.round((results.reduce((sum, r) => sum + (r.confidence ?? 0), 0) / results.length) * 100)
      : 0

  const chartData = [
    { name: 'Classified', count: classifiedCount, fill: 'hsl(258 90% 66%)' },
    { name: 'Unresolved', count: unresolvedCount, fill: 'hsl(0 72% 58%)' },
  ]

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Welcome back, {user?.full_name?.split(' ')[0]}</h1>
        <p className="text-sm text-muted-foreground">Here's what's happening in your organization.</p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard icon={Search} label="Classifications" value={history.data?.count ?? '—'} />
        <StatCard icon={Package} label="Products in catalog" value={products.data?.count ?? '—'} />
        <StatCard icon={CheckCircle2} label="Avg. confidence" value={`${avgConfidence}%`} hint="last 50 classifications" />
        <StatCard icon={TrendingUp} label="Your role" value={user?.role ?? '—'} />
      </div>

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Classification outcomes</CardTitle>
          </CardHeader>
          <CardContent>
            {results.length > 0 ? (
              <ResponsiveContainer width="100%" height={220}>
                <BarChart data={chartData}>
                  <XAxis dataKey="name" stroke="hsl(250 12% 65%)" fontSize={12} tickLine={false} axisLine={false} />
                  <YAxis stroke="hsl(250 12% 65%)" fontSize={12} tickLine={false} axisLine={false} allowDecimals={false} />
                  <Tooltip
                    contentStyle={{
                      background: 'hsl(250 30% 9%)',
                      border: '1px solid hsl(250 20% 18%)',
                      borderRadius: 8,
                      fontSize: 13,
                    }}
                  />
                  <Bar dataKey="count" radius={[6, 6, 0, 0]}>
                    {chartData.map((entry, i) => (
                      <Cell key={i} fill={entry.fill} />
                    ))}
                  </Bar>
                </BarChart>
              </ResponsiveContainer>
            ) : (
              <p className="py-10 text-center text-sm text-muted-foreground">
                No classifications yet.{' '}
                <Link to="/classify" className="text-primary hover:underline">
                  Classify your first product
                </Link>
              </p>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Quick actions</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2">
            <Link
              to="/classify"
              className="flex items-center gap-3 rounded-md border border-border p-3 text-sm transition-colors hover:bg-secondary/40"
            >
              <Search className="h-4 w-4 text-primary" />
              Classify a new product
            </Link>
            <Link
              to="/products"
              className="flex items-center gap-3 rounded-md border border-border p-3 text-sm transition-colors hover:bg-secondary/40"
            >
              <Package className="h-4 w-4 text-primary" />
              Manage your product catalog
            </Link>
          </CardContent>
        </Card>
      </div>
    </div>
  )
}
