import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AxiosError } from 'axios'
import { Plus, Loader2, Webhook as WebhookIcon, Trash2, Zap, Copy, Check } from 'lucide-react'
import { webhooksApi } from '@/lib/webhooks-api'
import { useToast } from '@/hooks/use-toast'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog'

const AVAILABLE_EVENTS = ['product.created', 'product.updated', 'product.deleted', 'classification.created']

const schema = z.object({
  url: z.string().url('Must be a valid URL'),
  event_types: z.array(z.string()).min(1, 'Select at least one event'),
})
type FormValues = z.infer<typeof schema>

export function WebhooksPage() {
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [newSecret, setNewSecret] = useState<string | null>(null)
  const [copied, setCopied] = useState(false)
  const [testResults, setTestResults] = useState<Record<number, { success: boolean; status_code: number | null }>>({})

  const { data: webhooks, isLoading } = useQuery({ queryKey: ['webhooks'], queryFn: webhooksApi.list })

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({ resolver: zodResolver(schema), defaultValues: { event_types: [] } })

  const createMutation = useMutation({
    mutationFn: webhooksApi.create,
    onSuccess: (webhook) => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] })
      setNewSecret(webhook.secret ?? null)
      reset({ url: '', event_types: [] })
      toast({ title: 'Webhook created' })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: webhooksApi.remove,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['webhooks'] })
      toast({ title: 'Webhook removed' })
    },
  })

  const testMutation = useMutation({
    mutationFn: webhooksApi.test,
    onSuccess: (result) => {
      toast({
        title: result.success ? 'Test delivery succeeded' : 'Test delivery failed',
        description: result.status_code ? `Responded with ${result.status_code}` : result.error ?? undefined,
        variant: result.success ? 'success' : 'destructive',
      })
    },
  })

  async function onSubmit(values: FormValues) {
    await createMutation.mutateAsync(values)
  }

  async function handleTest(id: number) {
    const result = await testMutation.mutateAsync(id)
    setTestResults((prev) => ({ ...prev, [id]: { success: result.success, status_code: result.status_code } }))
  }

  function copySecret() {
    if (newSecret) {
      navigator.clipboard.writeText(newSecret)
      setCopied(true)
      setTimeout(() => setCopied(false), 2000)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Webhooks</h1>
          <p className="text-sm text-muted-foreground">
            Get notified in real time when things happen in your organization.
          </p>
        </div>
        <Button
          onClick={() => {
            setNewSecret(null)
            reset({ url: '', event_types: [] })
            setDialogOpen(true)
          }}
        >
          <Plus className="mr-2 h-4 w-4" />
          Add webhook
        </Button>
      </div>

      {newSecret && (
        <Card className="border-primary/40 bg-primary/5">
          <CardContent className="pt-6">
            <p className="text-sm font-medium">Save this secret now — it won't be shown again.</p>
            <div className="mt-2 flex items-center gap-2">
              <code className="flex-1 truncate rounded bg-secondary px-3 py-2 text-xs">{newSecret}</code>
              <Button variant="outline" size="icon" onClick={copySecret}>
                {copied ? <Check className="h-4 w-4" /> : <Copy className="h-4 w-4" />}
              </Button>
            </div>
            <p className="mt-2 text-xs text-muted-foreground">
              Every delivery includes an <code>X-SYJ-Signature: sha256=...</code> header — verify it with HMAC-SHA256
              using this secret to confirm the payload really came from us.
            </p>
          </CardContent>
        </Card>
      )}

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : webhooks && webhooks.length > 0 ? (
        <div className="space-y-3">
          {webhooks.map((webhook) => (
            <Card key={webhook.id}>
              <CardContent className="flex items-center justify-between p-4">
                <div className="min-w-0 flex-1">
                  <p className="truncate font-mono text-sm">{webhook.url}</p>
                  <div className="mt-1 flex flex-wrap gap-1">
                    {webhook.event_types.map((e) => (
                      <Badge key={e} variant="secondary" className="text-[10px]">
                        {e}
                      </Badge>
                    ))}
                  </div>
                </div>
                <div className="ml-4 flex items-center gap-2">
                  {testResults[webhook.id] && (
                    <Badge variant={testResults[webhook.id].success ? 'success' : 'destructive'}>
                      {testResults[webhook.id].status_code ?? 'failed'}
                    </Badge>
                  )}
                  <Button variant="ghost" size="icon" onClick={() => handleTest(webhook.id)} disabled={testMutation.isPending}>
                    <Zap className="h-4 w-4" />
                  </Button>
                  <Button variant="ghost" size="icon" onClick={() => deleteMutation.mutate(webhook.id)}>
                    <Trash2 className="h-4 w-4 text-destructive" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-16 text-center">
          <WebhookIcon className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No webhooks configured yet.</p>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Add webhook</DialogTitle>
            <DialogDescription>We'll POST a signed JSON payload to this URL when the selected events happen.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="url">Endpoint URL</Label>
              <Input id="url" placeholder="https://example.com/webhook" {...register('url')} />
              {errors.url && <p className="text-xs text-destructive">{errors.url.message}</p>}
            </div>
            <div className="space-y-2">
              <Label>Events</Label>
              <Controller
                control={control}
                name="event_types"
                render={({ field }) => (
                  <div className="space-y-2">
                    {AVAILABLE_EVENTS.map((event) => (
                      <label key={event} className="flex items-center gap-2 text-sm">
                        <input
                          type="checkbox"
                          checked={field.value.includes(event)}
                          onChange={(e) => {
                            if (e.target.checked) field.onChange([...field.value, event])
                            else field.onChange(field.value.filter((v) => v !== event))
                          }}
                          className="h-4 w-4 rounded border-input"
                        />
                        <span className="font-mono text-xs">{event}</span>
                      </label>
                    ))}
                  </div>
                )}
              />
              {errors.event_types && <p className="text-xs text-destructive">{errors.event_types.message}</p>}
            </div>
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  Cancel
                </Button>
              </DialogClose>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                Create webhook
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
