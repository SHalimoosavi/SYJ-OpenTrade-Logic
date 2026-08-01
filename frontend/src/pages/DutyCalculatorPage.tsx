import { useState } from 'react'
import { useLocation } from 'react-router-dom'
import { useMutation } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AxiosError } from 'axios'
import { Calculator, Loader2, AlertTriangle, ExternalLink } from 'lucide-react'
import { dutyApi } from '@/lib/duty-api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import type { DutyCalculationResult } from '@/types/api'

const schema = z.object({
  hts_code: z.string().min(1, 'HTS code is required'),
  country_of_origin: z.string().length(2, 'Use a 2-letter country code, e.g. CN').transform((v) => v.toUpperCase()),
  declared_value: z.coerce.number().positive('Must be greater than 0'),
  general_duty_rate: z.string().optional(),
})
type FormValues = z.infer<typeof schema>

function formatCurrency(n: number | null) {
  if (n === null) return '—'
  return n.toLocaleString('en-US', { style: 'currency', currency: 'USD' })
}

function formatPercent(n: number | null) {
  if (n === null) return '—'
  return `${(n * 100).toFixed(2)}%`
}

export function DutyCalculatorPage() {
  const location = useLocation()
  const handoff = (location.state as { hts_code?: string; general_duty_rate?: string } | null) ?? null

  const [result, setResult] = useState<DutyCalculationResult | null>(null)
  const [serverError, setServerError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
  } = useForm<FormValues>({
    resolver: zodResolver(schema),
    defaultValues: {
      hts_code: handoff?.hts_code ?? '',
      general_duty_rate: handoff?.general_duty_rate ?? '',
    },
  })

  const mutation = useMutation({
    mutationFn: dutyApi.calculate,
    onSuccess: (data) => {
      setResult(data)
      setServerError(null)
    },
  })

  async function onSubmit(values: FormValues) {
    setServerError(null)
    try {
      await mutation.mutateAsync(values)
    } catch (err) {
      const message = err instanceof AxiosError && err.response?.data?.detail ? err.response.data.detail : 'Calculation failed.'
      setServerError(typeof message === 'string' ? message : 'Calculation failed.')
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Duty calculator</h1>
        <p className="text-sm text-muted-foreground">
          Estimate total duty for an HTS code, including applicable Section 301/232 trade remedies and AD/CVD scope flags.
        </p>
      </div>

      {handoff?.hts_code && (
        <div className="rounded-md border border-primary/30 bg-primary/5 px-4 py-2 text-sm text-muted-foreground">
          Pre-filled from your classification of <span className="font-mono text-foreground">{handoff.hts_code}</span> — just add the country of origin and declared value.
        </div>
      )}

      <div className="flex items-start gap-3 rounded-md border border-destructive/30 bg-destructive/10 p-4 text-sm">
        <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-destructive" />
        <p className="text-muted-foreground">
          This is an <strong>estimation tool</strong>, not legal, customs, or financial advice. Trade remedy duties
          change frequently, sometimes with only days of notice. Always verify against the official CBP/USTR sources
          before making an import decision, or consult a licensed customs broker.
        </p>
      </div>

      <Card>
        <CardContent className="pt-6">
          <form onSubmit={handleSubmit(onSubmit)} className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-2">
              <Label htmlFor="hts_code">HTS code</Label>
              <Input id="hts_code" placeholder="8467.21.00.10" {...register('hts_code')} />
              {errors.hts_code && <p className="text-xs text-destructive">{errors.hts_code.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="country_of_origin">Country of origin</Label>
              <Input id="country_of_origin" placeholder="CN" maxLength={2} {...register('country_of_origin')} />
              {errors.country_of_origin && <p className="text-xs text-destructive">{errors.country_of_origin.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="declared_value">Declared value (USD)</Label>
              <Input id="declared_value" type="number" step="0.01" placeholder="10000" {...register('declared_value')} />
              {errors.declared_value && <p className="text-xs text-destructive">{errors.declared_value.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="general_duty_rate">Base HTS duty rate (optional)</Label>
              <Input id="general_duty_rate" placeholder="1.7% or Free" {...register('general_duty_rate')} />
            </div>
            {serverError && <p className="col-span-2 text-sm text-destructive">{serverError}</p>}
            <div className="col-span-2">
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting ? <Loader2 className="mr-2 h-4 w-4 animate-spin" /> : <Calculator className="mr-2 h-4 w-4" />}
                Calculate
              </Button>
            </div>
          </form>
        </CardContent>
      </Card>

      {result && (
        <Card className="animate-in fade-in-0 slide-in-from-top-2 duration-300">
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>
                {result.hts_code} from {result.country_of_origin}
              </span>
              <span className="font-mono text-primary">{formatCurrency(result.total_duty_amount)}</span>
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-5">
            <div className="grid grid-cols-2 gap-4 text-sm sm:grid-cols-4">
              <div>
                <p className="text-muted-foreground">Declared value</p>
                <p className="font-mono font-medium">{formatCurrency(result.declared_value)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Base rate</p>
                <p className="font-mono font-medium">
                  {result.base_rate_raw ?? '—'} {result.base_duty_amount !== null && `(${formatCurrency(result.base_duty_amount)})`}
                </p>
              </div>
              <div>
                <p className="text-muted-foreground">Total rate</p>
                <p className="font-mono font-medium">{formatPercent(result.total_duty_rate)}</p>
              </div>
              <div>
                <p className="text-muted-foreground">Total duty</p>
                <p className="font-mono font-medium text-primary">{formatCurrency(result.total_duty_amount)}</p>
              </div>
            </div>

            {result.program_duties.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">Applicable trade remedy programs</h3>
                <div className="space-y-2">
                  {result.program_duties.map((p, i) => (
                    <div key={i} className="rounded-md border border-border p-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{p.program}</span>
                        <span className="font-mono">
                          +{(p.rate * 100).toFixed(1)}% = {formatCurrency(p.amount)}
                        </span>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">
                        {p.chapter99_code} · {p.legal_basis}
                      </p>
                      <p className="mt-1 text-xs text-muted-foreground">{p.notes}</p>
                      <a
                        href={p.source_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="mt-1 inline-flex items-center gap-1 text-xs text-primary hover:underline"
                      >
                        Official source <ExternalLink className="h-3 w-3" />
                      </a>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.adcvd_flags.length > 0 && (
              <div>
                <h3 className="mb-2 flex items-center gap-2 text-sm font-medium text-destructive">
                  <AlertTriangle className="h-4 w-4" />
                  AD/CVD scope flags — verify before importing
                </h3>
                <div className="space-y-2">
                  {result.adcvd_flags.map((f, i) => (
                    <div key={i} className="rounded-md border border-destructive/30 bg-destructive/5 p-3 text-sm">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">{f.product_scope}</span>
                        <div className="flex gap-1">
                          {f.case_numbers.map((c) => (
                            <Badge key={c} variant="destructive" className="font-mono text-[10px]">
                              {c}
                            </Badge>
                          ))}
                        </div>
                      </div>
                      <p className="mt-1 text-xs text-muted-foreground">{f.notes}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.warnings.length > 0 && (
              <div className="space-y-1">
                {result.warnings.map((w, i) => (
                  <p key={i} className="text-xs text-muted-foreground">
                    ⚠ {w}
                  </p>
                ))}
              </div>
            )}

            <div className="border-t border-border pt-4 text-xs text-muted-foreground">
              <p>Data as of {result.as_of_date}. {result.disclaimer}</p>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
