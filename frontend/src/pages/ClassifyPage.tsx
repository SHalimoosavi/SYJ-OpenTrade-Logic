import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { useMutation, useQuery } from '@tanstack/react-query'
import { Search, Loader2, CheckCircle2, XCircle, ChevronRight, Scale, FileDown, Calculator } from 'lucide-react'
import { classifyApi } from '@/lib/classify-api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Card, CardContent, CardHeader, CardTitle } from '@/components/ui/card'
import { reportsApi } from '@/lib/reports-api'
import { Badge } from '@/components/ui/badge'
import type { ClassificationResult } from '@/types/api'

export function ClassifyPage() {
  const navigate = useNavigate()
  const [description, setDescription] = useState('')
  const [result, setResult] = useState<ClassificationResult | null>(null)

  const mutation = useMutation({
    mutationFn: (desc: string) => classifyApi.classify(desc),
    onSuccess: (data) => setResult(data),
  })

  const history = useQuery({
    queryKey: ['classification-history'],
    queryFn: () => classifyApi.history(10),
  })

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault()
    if (description.trim()) mutation.mutate(description.trim())
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-2xl font-semibold">Classify a product</h1>
        <p className="text-sm text-muted-foreground">
          Enter a plain-language product description. Every result shows the full GRI decision path — never a black-box guess.
        </p>
      </div>

      <form onSubmit={handleSubmit} className="flex gap-3">
        <div className="relative flex-1">
          <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
          <Input
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="e.g. cordless electric drill"
            className="pl-9"
          />
        </div>
        <Button type="submit" disabled={mutation.isPending || !description.trim()}>
          {mutation.isPending ? <Loader2 className="h-4 w-4 animate-spin" /> : 'Classify'}
        </Button>
      </form>

      {result && (
        <Card className="animate-in fade-in-0 slide-in-from-top-2 duration-300">
          <CardHeader>
            <div className="flex items-start justify-between">
              <div>
                <CardTitle className="flex items-center gap-2">
                  {result.is_classified ? (
                    <CheckCircle2 className="h-5 w-5 text-success" />
                  ) : (
                    <XCircle className="h-5 w-5 text-destructive" />
                  )}
                  {result.is_classified ? result.final_code : 'Unresolved'}
                </CardTitle>
                <p className="mt-1 text-sm text-muted-foreground">{result.final_description ?? result.unresolved_reason}</p>
              </div>
              {result.is_classified && (
                <div className="flex items-center gap-3">
                  <div className="text-right">
                    <p className="text-xs text-muted-foreground">Confidence</p>
                    <p className="font-mono text-lg font-semibold text-primary">
                      {Math.round(result.confidence * 100)}%
                    </p>
                  </div>
                  <Button
                    variant="outline"
                    size="icon"
                    title="Calculate duty for this classification"
                    onClick={() =>
                      navigate('/duty-calculator', {
                        state: { hts_code: result.final_code, general_duty_rate: result.duty_rate },
                      })
                    }
                  >
                    <Calculator className="h-4 w-4" />
                  </Button>
                  {result.id && (
                    <Button variant="outline" size="icon" onClick={() => reportsApi.downloadClassificationPdf(result.id!)}>
                      <FileDown className="h-4 w-4" />
                    </Button>
                  )}
                </div>
              )}
            </div>
          </CardHeader>
          <CardContent className="space-y-6">
            {result.duty_rate && (
              <div className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Duty rate:</span>
                <Badge variant="success" className="font-mono">
                  {result.duty_rate}
                </Badge>
              </div>
            )}

            {result.decision_path.length > 0 && (
              <div>
                <h3 className="mb-3 text-sm font-medium text-muted-foreground">Decision path</h3>
                <div className="space-y-3">
                  {result.decision_path.map((step, i) => (
                    <div key={i} className="flex gap-3 rounded-md border border-border bg-secondary/30 p-3">
                      <div className="flex flex-col items-center">
                        <Badge variant="outline" className="mb-1 font-mono">
                          {step.rule_applied}
                        </Badge>
                        {i < result.decision_path.length - 1 && (
                          <ChevronRight className="h-4 w-4 rotate-90 text-muted-foreground" />
                        )}
                      </div>
                      <div className="flex-1">
                        <p className="font-mono text-sm font-medium">{step.node_code}</p>
                        <p className="text-sm text-muted-foreground">{step.node_description}</p>
                        <p className="mt-1 text-xs text-muted-foreground/80">{step.reasoning}</p>
                      </div>
                      <div className="font-mono text-xs text-muted-foreground">{step.score.toFixed(2)}</div>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.alternatives.length > 0 && (
              <div>
                <h3 className="mb-3 text-sm font-medium text-muted-foreground">Alternatives considered</h3>
                <div className="space-y-2">
                  {result.alternatives.map((alt, i) => (
                    <div key={i} className="flex items-center justify-between rounded-md border border-border px-3 py-2 text-sm">
                      <div>
                        <span className="font-mono">{alt.code}</span>
                        <span className="ml-2 text-muted-foreground">{alt.description}</span>
                      </div>
                      <Badge variant="secondary" className="font-mono">
                        {Math.round(alt.confidence * 100)}%
                      </Badge>
                    </div>
                  ))}
                </div>
              </div>
            )}

            {result.supporting_notes.length > 0 && (
              <div>
                <h3 className="mb-2 text-sm font-medium text-muted-foreground">Supporting legal notes</h3>
                <ul className="space-y-1 text-sm text-muted-foreground">
                  {result.supporting_notes.map((note, i) => (
                    <li key={i} className="border-l-2 border-border pl-3">
                      {note}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.related_rulings && result.related_rulings.length > 0 && (
              <div>
                <h3 className="mb-3 flex items-center gap-2 text-sm font-medium text-muted-foreground">
                  <Scale className="h-4 w-4" />
                  Related CBP CROSS rulings
                </h3>
                <p className="mb-3 text-xs text-muted-foreground/70">
                  Surfaced as supporting precedent for a human to review — never used to override the classification above.
                </p>
                <div className="space-y-2">
                  {result.related_rulings.map((ruling) => (
                    <a
                      key={ruling.id}
                      href={ruling.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="block rounded-md border border-border p-3 text-sm transition-colors hover:bg-secondary/40"
                    >
                      <div className="flex items-center justify-between">
                        <span className="font-mono font-medium text-primary">{ruling.id}</span>
                        <span className="text-xs text-muted-foreground">{ruling.date}</span>
                      </div>
                      <p className="mt-1 text-muted-foreground">{ruling.title}</p>
                      {ruling.gri_rules_cited.length > 0 && (
                        <div className="mt-2 flex flex-wrap gap-1">
                          {ruling.gri_rules_cited.map((rule) => (
                            <Badge key={rule} variant="outline" className="font-mono text-[10px]">
                              {rule}
                            </Badge>
                          ))}
                        </div>
                      )}
                    </a>
                  ))}
                </div>
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {history.data && history.data.results.length > 0 && (
        <div>
          <h2 className="mb-3 text-sm font-medium text-muted-foreground">Recent classifications</h2>
          <div className="space-y-2">
            {history.data.results.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  setDescription(item.product_description)
                }}
                className="flex w-full items-center justify-between rounded-md border border-border px-4 py-3 text-left text-sm transition-colors hover:bg-secondary/40"
              >
                <span className="truncate">{item.product_description}</span>
                {item.is_classified ? (
                  <Badge variant="secondary" className="ml-3 shrink-0 font-mono">
                    {item.final_code}
                  </Badge>
                ) : (
                  <Badge variant="destructive" className="ml-3 shrink-0">
                    Unresolved
                  </Badge>
                )}
              </button>
            ))}
          </div>
        </div>
      )}
    </div>
  )
}
