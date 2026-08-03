import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useForm, Controller } from 'react-hook-form'
import { zodResolver } from '@hookform/resolvers/zod'
import { z } from 'zod'
import { AxiosError } from 'axios'
import { UserPlus, Loader2, Users } from 'lucide-react'
import { orgApi } from '@/lib/org-api'
import { useAuth } from '@/lib/auth-context'
import { useToast } from '@/hooks/use-toast'
import { roleAtLeast, type UserRole } from '@/types/api'
import { Button } from '@/components/ui/button'
import { Input } from '@/components/ui/input'
import { Label } from '@/components/ui/label'
import { Badge } from '@/components/ui/badge'
import { Table, TableHeader, TableBody, TableRow, TableHead, TableCell } from '@/components/ui/table'
import { Select, SelectTrigger, SelectValue, SelectContent, SelectItem } from '@/components/ui/select'
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
  DialogClose,
} from '@/components/ui/dialog'

const inviteSchema = z.object({
  full_name: z.string().min(1, 'Name is required'),
  email: z.string().min(3, 'Email is required'),
  password: z.string().min(8, 'Password must be at least 8 characters'),
  role: z.enum(['viewer', 'member', 'admin', 'owner']),
})
type InviteFormValues = z.infer<typeof inviteSchema>

const roleBadgeVariant: Record<UserRole, 'default' | 'secondary' | 'outline'> = {
  owner: 'default',
  admin: 'default',
  member: 'secondary',
  viewer: 'outline',
}

export function MembersPage() {
  const { user } = useAuth()
  const queryClient = useQueryClient()
  const { toast } = useToast()
  const [dialogOpen, setDialogOpen] = useState(false)
  const [formError, setFormError] = useState<string | null>(null)

  const canInvite = user ? roleAtLeast(user.role, 'admin') : false
  const canChangeRoles = canInvite

  const { data: members, isLoading } = useQuery({ queryKey: ['org-members'], queryFn: orgApi.listMembers })

  const {
    register,
    handleSubmit,
    control,
    reset,
    formState: { errors, isSubmitting },
  } = useForm<InviteFormValues>({ resolver: zodResolver(inviteSchema), defaultValues: { role: 'member' } })

  const inviteMutation = useMutation({
    mutationFn: orgApi.inviteMember,
    onSuccess: (member) => {
      queryClient.invalidateQueries({ queryKey: ['org-members'] })
      setDialogOpen(false)
      reset()
      toast({ title: 'Member invited', description: `${member.email} can now sign in.` })
    },
  })

  const roleMutation = useMutation({
    mutationFn: ({ userId, role }: { userId: number; role: UserRole }) => orgApi.updateRole(userId, role),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['org-members'] })
      toast({ title: 'Role updated' })
    },
    onError: () => {
      toast({ variant: 'destructive', title: 'Could not update role' })
    },
  })

  async function onSubmit(values: InviteFormValues) {
    setFormError(null)
    try {
      await inviteMutation.mutateAsync(values)
    } catch (err) {
      const message = err instanceof AxiosError && err.response?.data?.detail ? err.response.data.detail : 'Invite failed.'
      setFormError(message)
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Members</h1>
          <p className="text-sm text-muted-foreground">People in your organization and their access level.</p>
        </div>
        {canInvite && (
          <Button
            onClick={() => {
              setFormError(null)
              reset({ full_name: '', email: '', password: '', role: 'member' })
              setDialogOpen(true)
            }}
          >
            <UserPlus className="mr-2 h-4 w-4" />
            Invite member
          </Button>
        )}
      </div>

      {isLoading ? (
        <div className="flex justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : members && members.length > 0 ? (
        <div className="rounded-lg border border-border">
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Name</TableHead>
                <TableHead>Email</TableHead>
                <TableHead>Role</TableHead>
                {canChangeRoles && <TableHead className="text-right">Change role</TableHead>}
              </TableRow>
            </TableHeader>
            <TableBody>
              {members.map((member) => (
                <TableRow key={member.id}>
                  <TableCell>{member.full_name}</TableCell>
                  <TableCell className="text-muted-foreground">{member.email}</TableCell>
                  <TableCell>
                    <Badge variant={roleBadgeVariant[member.role]} className="capitalize">
                      {member.role}
                    </Badge>
                  </TableCell>
                  {canChangeRoles && (
                    <TableCell className="text-right">
                      <Select
                        value={member.role}
                        onValueChange={(newRole) => roleMutation.mutate({ userId: member.id, role: newRole as UserRole })}
                        disabled={member.id === user?.id && member.role === 'owner'}
                      >
                        <SelectTrigger className="ml-auto w-32">
                          <SelectValue />
                        </SelectTrigger>
                        <SelectContent>
                          <SelectItem value="viewer">Viewer</SelectItem>
                          <SelectItem value="member">Member</SelectItem>
                          <SelectItem value="admin">Admin</SelectItem>
                          <SelectItem value="owner">Owner</SelectItem>
                        </SelectContent>
                      </Select>
                    </TableCell>
                  )}
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </div>
      ) : (
        <div className="flex flex-col items-center gap-3 rounded-lg border border-dashed border-border py-16 text-center">
          <Users className="h-8 w-8 text-muted-foreground" />
          <p className="text-sm text-muted-foreground">No members found.</p>
        </div>
      )}

      <Dialog open={dialogOpen} onOpenChange={setDialogOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Invite member</DialogTitle>
            <DialogDescription>They'll be able to sign in immediately with the password you set here.</DialogDescription>
          </DialogHeader>
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="full_name">Full name</Label>
              <Input id="full_name" {...register('full_name')} />
              {errors.full_name && <p className="text-xs text-destructive">{errors.full_name.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">Email</Label>
              <Input id="email" type="email" {...register('email')} />
              {errors.email && <p className="text-xs text-destructive">{errors.email.message}</p>}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">Temporary password</Label>
              <Input id="password" type="password" {...register('password')} />
              {errors.password && <p className="text-xs text-destructive">{errors.password.message}</p>}
            </div>
            <div className="space-y-2">
              <Label>Role</Label>
              <Controller
                control={control}
                name="role"
                render={({ field }) => (
                  <Select value={field.value} onValueChange={field.onChange}>
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="viewer">Viewer — read only</SelectItem>
                      <SelectItem value="member">Member — create/edit products</SelectItem>
                      <SelectItem value="admin">Admin — + delete, manage members</SelectItem>
                      <SelectItem value="owner">Owner — full access</SelectItem>
                    </SelectContent>
                  </Select>
                )}
              />
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
                Send invite
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>
    </div>
  )
}
