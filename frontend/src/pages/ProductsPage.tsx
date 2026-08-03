import { useState, useRef } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AxiosError } from 'axios'
import { Plus, Upload, Download, Trash2, Pencil, Loader2, Package, ChevronLeft, ChevronRight } from 'lucide-react'
import { reportsApi } from '@/lib/reports-api'
import { productsApi } from '@/lib/products-api'
import { useAuth } from '@/lib/auth-context'
import { useToast } from '@/hooks/use-toast'
import { roleAtLeast, type Product, type ImportSummary } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Skeleton } from '@/components/ui/skeleton'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog'

const PAGE_SIZE = 20

const productSchema = z.object({
  sku: z.string().min(1, 'SKU is required'),
  name: z.string().min(1, 'Name is required'),
  hts_code: z.string().optional(),
  duty_rate: z.string().optional(),
  description: z.string().optional(),
})
type ProductFormValues = z.infer<typeof productSchema>

export function ProductsPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const fileInputRef = useRef<HTMLInputElement>(null)

  const [page, setPage] = useState(0)
  const [dialogOpen, setDialogOpen] = useState(false)
  const [editingProduct, setEditingProduct] = useState<Product | null>(null)
  const [importSummary, setImportSummary] = useState<ImportSummary | null>(null)
  const [formError, setFormError] = useState<string | null>(null)

  const canWrite = user ? roleAtLeast(user.role, 'member') : false
  const canDelete = user ? roleAtLeast(user.role, 'admin') : false

  const { data, isLoading } = useQuery({
    queryKey: ['products', page],
    queryFn: () => productsApi.list(PAGE_SIZE, page * PAGE_SIZE),
  })

  const totalPages = data ? Math.max(1, Math.ceil(data.count / PAGE_SIZE)) : 1

  const {
    register,
    handleSubmit,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<ProductFormValues>({ resolver: zodResolver(productSchema) })

  const createMutation = useMutation({
    mutationFn: productsApi.create,
    onSuccess: (product) => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      setDialogOpen(false)
      toast({ title: 'Product added', description: `${product.sku} — ${product.name}` })
    },
  })

  const updateMutation = useMutation({
    mutationFn: ({ id, payload }: { id: number; payload: ProductFormValues }) => productsApi.update(id, payload),
    onSuccess: (product) => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      setDialogOpen(false)
      toast({ title: 'Product updated', description: `${product.sku} — ${product.name}` })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: productsApi.remove,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['products'] })
      toast({ title: 'Product deleted' })
    },
    onError: () => {
      toast({ variant: 'destructive', title: 'Could not delete product' })
    },
  })

  const importMutation = useMutation({
    mutationFn: productsApi.importFile,
    onSuccess: (summary) => {
      setImportSummary(summary)
      queryClient.invalidateQueries({ queryKey: ['products'] })
      toast({
        title: 'Import complete',
        description: `${summary.created} created, ${summary.updated} updated, ${summary.errors} errors`,
        variant: summary.errors > 0 ? 'destructive' : 'success',
      })
    },
    onError: () => {
      toast({ variant: 'destructive', title: 'Import failed', description: 'Check the file format and try again.' })
    },
  })

  function openCreateDialog() {
    setEditingProduct(null)
    setFormError(null)
    reset({ sku: '', name: '', hts_code: '', duty_rate: '', description: '' })
    setDialogOpen(true)
  }

  function openEditDialog(product: Product) {
    setEditingProduct(product)
    setFormError(null)
    reset({
      sku: product.sku,
      name: product.name,
      hts_code: product.hts_code ?? '',
      duty_rate: product.duty_rate ?? '',
      description: product.description ?? '',
    })
    setDialogOpen(true)
  }

  async function onSubmit(values: ProductFormValues) {
    setFormError(null)
    try {
      if (editingProduct) {
        await updateMutation.mutateAsync({ id: editingProduct.id, payload: values })
      } else {
        await createMutation.mutateAsync(values)
      }
    } catch (err) {
      const message = err instanceof AxiosError && err.response?.data?.detail ? err.response.data.detail : 'Save failed.'
      setFormError(message)
    }
  }

  function handleFileSelected(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0]
    if (file) importMutation.mutate(file)
    e.target.value = ''
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Product catalog</h1>
          <p className="text-sm text-muted-foreground">{data?.count ?? 0} products in your organization.</p>
        </div>
        {canWrite && (
          <div className="flex flex-wrap gap-2">
            <input ref={fileInputRef} type="file" accept=".csv,.xlsx" className="hidden" onChange={handleFileSelected} />
            <Button variant="outline" size="sm" onClick={() => fileInputRef.current?.click()} disabled={importMutation.isPending}>
              {importMutation.isPending ? (
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
              ) : (
                <Upload className="mr-2 h-4 w-4" />
              )}
              Import
            </Button>
            <Button variant="outline" size="sm" onClick={() => reportsApi.downloadProductsCsv()}>
              <Download className="mr-2 h-4 w-4" />
              CSV
            </Button>
            <Button variant="outline" size="sm" onClick={() => reportsApi.downloadProductsExcel()}>
              <Download className="mr-2 h-4 w-4" />
              Excel
            </Button>
            <Button size="sm" onClick={openCreateDialog}>
              <Plus className="mr-2 h-4 w-4" />
              Add product
            </Button>
          </div>
        )}
      </div>

      {importSummary && (
        <div className="rounded-md border border-border bg-secondary/30 p-4 text-sm">
          <p className="font-medium">
            Import complete: {importSummary.created} created, {importSummary.updated} updated, {importSummary.errors} errors
            out of {importSummary.total_rows} rows.
          </p>
          {importSummary.errors > 0 && (
            <ul className="mt-2 space-y-1 text-xs text-destructive">
              {importSummary.row_results
                .filter((r) => r.status === 'error')
                .map((r) => (
                  <li key={r.row_number}>
                    Row {r.row_number}: {r.error}
                  </li>
                ))}
            </ul>
          )}
        </div>
      )}

      {isLoading ? (
        <div className="space-y-2 rounded-lg border border-border p-4">
          {Array.from({ length: 5 }).map((_, i) => (
            <Skeleton key={i} className="h-10 w-full" />
          ))}
        </div>
      ) : data && data.results.length > 0 ? (
        <>
          <div className="rounded-lg border border-border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>SKU</TableHead>
                  <TableHead>Name</TableHead>
                  <TableHead>HTS Code</TableHead>
                  <TableHead>Duty Rate</TableHead>
                  {(canWrite || canDelete) && <TableHead className="text-right">Actions</TableHead>}
                </TableRow>
              </TableHeader>
              <TableBody>
                {data.results.map((product) => (
                  <TableRow key={product.id}>
                    <TableCell className="font-mono text-sm">{product.sku}</TableCell>
                    <TableCell>{product.name}</TableCell>
                    <TableCell className="font-mono text-sm">
                      {product.hts_code ? <Badge variant="outline">{product.hts_code}</Badge> : '—'}
                    </TableCell>
                    <TableCell className="font-mono text-sm">{product.duty_rate ?? '—'}</TableCell>
                    {(canWrite || canDelete) && (
                      <TableCell className="text-right">
                        <div className="flex justify-end gap-1">
                          {canWrite && (
                            <Button variant="ghost" size="icon" onClick={() => openEditDialog(product)}>
                              <Pencil className="h-4 w-4" />
                            </Button>
                          )}
                          {canDelete && (
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => deleteMutation.mutate(product.id)}
                              disabled={deleteMutation.isPending}
                            >
                              <Trash2 className="h-4 w-4 text-destructive" />
                            </Button>
                          )}
                        </div>
                      </TableCell>
                    )}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>

          {totalPages > 1 && (
            <div className="flex items-center justify-between text-sm text-muted-foreground">
              <span>
                Page {page + 1} of {totalPages}
              </span>
              <div className="flex gap-2">
                <Button variant="outline" size="sm" onClick={() => setPage((p) => Math.max(0, p - 1))} disabled={page === 0}>
                  <ChevronLeft className="h-4 w-4" />
                </Button>
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setPage((p) => Math.min(totalPages - 1, p + 1))}
                  disabled={page >= totalPages - 1}
                >
                  <ChevronRight className="h-4 w-4" />
                </Button>
              </div>
            </div>
          )}
        </>
      ) : (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-16 text-center">
          <Package className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No products yet. Add one manually or import a CSV/Excel file.</p>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{editingProduct ? 'Edit product' : 'Add product'}</DialogTitle>
            <DialogDescription>
              {editingProduct ? 'Update this product\'s details.' : 'Add a new product to your catalog.'}
            </DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="sku">SKU</Label>
              <Input id="sku" {...register('sku')} disabled={!!editingProduct} />
              {errors.sku && <p className="text-xs text-destructive">{errors.sku.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="name">Name</Label>
              <Input id="name" {...register('name')} />
              {errors.name && <p className="text-xs text-destructive">{errors.name.message}</p>}
            </div>
            <div className="grid grid-cols-2 gap-4">
              <div className="space-y-2">
                <Label htmlFor="hts_code">HTS code</Label>
                <Input id="hts_code" placeholder="8467.21.00.10" {...register('hts_code')} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="duty_rate">Duty rate</Label>
                <Input id="duty_rate" placeholder="Free" {...register('duty_rate')} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="description">Description</Label>
              <Input id="description" {...register('description')} />
            </div>
            {formError && <p className="text-sm text-destructive">{formError}</p>}
            <DialogFooter>
              <DialogClose asChild>
                <Button type="button" variant="outline">
                  Cancel
                </Button>
              </DialogClose>
              <Button type="submit" disabled={isSubmitting}>
                {isSubmitting && <Loader2 className="mr-2 h-4 w-4 animate-spin" />}
                {editingProduct ? 'Save changes' : 'Add product'}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
