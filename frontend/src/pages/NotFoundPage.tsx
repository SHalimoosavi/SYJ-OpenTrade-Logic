import { Link } from 'react-router-dom'
import { Compass } from 'lucide-react'
import { Button } from '@/components/ui/button'

export function NotFoundPage() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center gap-4 bg-background px-4 text-center">
      <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/15 text-primary">
        <Compass className="h-7 w-7" />
      </div>
      <div>
        <h1 className="text-3xl font-semibold">404</h1>
        <p className="mt-1 text-sm text-muted-foreground">This page doesn't exist, or you don't have access to it.</p>
      </div>
      <Button asChild>
        <Link to="/">Back to overview</Link>
      </Button>
    </div>
  )
}
