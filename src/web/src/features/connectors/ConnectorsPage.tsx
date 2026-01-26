import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Link2, Plus, Trash2, RefreshCw, Settings, Loader2, CheckCircle, XCircle, AlertCircle } from 'lucide-react'
import { connectorsApi } from '@/api'
import type { ConnectorType, ConnectorScope } from '@/models'
import {
  Button,
  Card,
  CardContent,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
  Input,
  Label,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Textarea,
} from '@/components/ui'
import { cn } from '@/lib/utils'

const connectorTypeLabels: Record<string, string> = {
  CONNECTOR_TYPE_TEAMS: 'Microsoft Teams',
  CONNECTOR_TYPE_GOOGLE_DRIVE: 'Google Drive',
  CONNECTOR_TYPE_ONEDRIVE: 'OneDrive',
  CONNECTOR_TYPE_WEB: 'Web Crawler',
  CONNECTOR_TYPE_FILE: 'File Upload',
}

// Map enum string names to integer values (matching Python proto enums)
const connectorTypeValues: Record<string, number> = {
  CONNECTOR_TYPE_UNSPECIFIED: 0,
  CONNECTOR_TYPE_TEAMS: 1,
  CONNECTOR_TYPE_GOOGLE_DRIVE: 2,
  CONNECTOR_TYPE_ONEDRIVE: 3,
  CONNECTOR_TYPE_WEB: 4,
  CONNECTOR_TYPE_FILE: 5,
}

const connectorScopeValues: Record<string, number> = {
  CONNECTOR_SCOPE_UNSPECIFIED: 0,
  CONNECTOR_SCOPE_USER: 1,
  CONNECTOR_SCOPE_GROUP: 2,
  CONNECTOR_SCOPE_ORG: 3,
}

const statusIcons: Record<string, typeof CheckCircle> = {
  CONNECTOR_STATUS_ACTIVE: CheckCircle,
  CONNECTOR_STATUS_SYNCING: RefreshCw,
  CONNECTOR_STATUS_ERROR: XCircle,
  CONNECTOR_STATUS_PENDING: AlertCircle,
  CONNECTOR_STATUS_DISABLED: XCircle,
}

const statusColors: Record<string, string> = {
  CONNECTOR_STATUS_ACTIVE: 'text-green-500',
  CONNECTOR_STATUS_SYNCING: 'text-blue-500 animate-spin',
  CONNECTOR_STATUS_ERROR: 'text-red-500',
  CONNECTOR_STATUS_PENDING: 'text-yellow-500',
  CONNECTOR_STATUS_DISABLED: 'text-gray-500',
}

export function ConnectorsPage() {
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [newConnector, setNewConnector] = useState({
    name: '',
    type: 'CONNECTOR_TYPE_WEB',
    config: '{}',
    refreshFreqMinutes: 1440,
    scope: 'CONNECTOR_SCOPE_USER',
  })

  const { data: connectorsData, isLoading } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => connectorsApi.list(),
  })

  const connectors = connectorsData?.connectors || []

  const createMutation = useMutation({
    mutationFn: connectorsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
      setIsCreateOpen(false)
      setNewConnector({
        name: '',
        type: 'CONNECTOR_TYPE_WEB',
        config: '{}',
        refreshFreqMinutes: 1440,
        scope: 'CONNECTOR_SCOPE_USER',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: connectorsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
      setDeleteId(null)
    },
  })

  const syncMutation = useMutation({
    mutationFn: connectorsApi.triggerSync,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['connectors'] })
    },
  })

  const handleCreate = () => {
    let config = {}
    try {
      config = JSON.parse(newConnector.config)
    } catch {
      // Invalid JSON, use empty object
    }

    createMutation.mutate({
      name: newConnector.name,
      type: connectorTypeValues[newConnector.type] as unknown as ConnectorType,
      config,
      refreshFreqMinutes: newConnector.refreshFreqMinutes,
      scope: connectorScopeValues[newConnector.scope] as unknown as ConnectorScope,
    })
  }

  const handleDelete = () => {
    if (deleteId) {
      deleteMutation.mutate(deleteId)
    }
  }

  return (
    <div className="h-full overflow-auto">
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Connectors</h1>
            <p className="text-muted-foreground">
              Manage data source connections for document ingestion
            </p>
          </div>
          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Connector
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Create Connector</DialogTitle>
                <DialogDescription>
                  Add a new data source connector to ingest documents.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={newConnector.name}
                    onChange={(e) => setNewConnector({ ...newConnector, name: e.target.value })}
                    placeholder="My Connector"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Type</Label>
                  <Select
                    value={newConnector.type}
                    onValueChange={(v) => setNewConnector({ ...newConnector, type: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="CONNECTOR_TYPE_WEB">Web Crawler</SelectItem>
                      <SelectItem value="CONNECTOR_TYPE_FILE">File Upload</SelectItem>
                      <SelectItem value="CONNECTOR_TYPE_GOOGLE_DRIVE">Google Drive</SelectItem>
                      <SelectItem value="CONNECTOR_TYPE_ONEDRIVE">OneDrive</SelectItem>
                      <SelectItem value="CONNECTOR_TYPE_TEAMS">Microsoft Teams</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Scope</Label>
                  <Select
                    value={newConnector.scope}
                    onValueChange={(v) => setNewConnector({ ...newConnector, scope: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="CONNECTOR_SCOPE_USER">User</SelectItem>
                      <SelectItem value="CONNECTOR_SCOPE_GROUP">Group</SelectItem>
                      <SelectItem value="CONNECTOR_SCOPE_ORG">Organization</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Refresh Frequency (minutes)</Label>
                  <Input
                    type="number"
                    value={newConnector.refreshFreqMinutes}
                    onChange={(e) =>
                      setNewConnector({ ...newConnector, refreshFreqMinutes: Number(e.target.value) })
                    }
                  />
                </div>
                <div className="space-y-2">
                  <Label>Configuration (JSON)</Label>
                  <Textarea
                    value={newConnector.config}
                    onChange={(e) => setNewConnector({ ...newConnector, config: e.target.value })}
                    placeholder='{"url": "https://example.com"}'
                    rows={4}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
                  Cancel
                </Button>
                <Button onClick={handleCreate} disabled={!newConnector.name || createMutation.isPending}>
                  {createMutation.isPending ? 'Creating...' : 'Create'}
                </Button>
              </DialogFooter>
            </DialogContent>
          </Dialog>
        </div>

        <Card>
          <CardContent className="pt-6">
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : connectors.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Link2 className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No connectors configured</p>
                <p className="text-sm">Add a connector to start ingesting documents.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Type</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead>Documents</TableHead>
                    <TableHead>Last Sync</TableHead>
                    <TableHead className="w-[150px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {connectors.map((connector) => {
                    const StatusIcon = statusIcons[connector.status] || AlertCircle
                    return (
                      <TableRow key={connector.id}>
                        <TableCell className="font-medium">{connector.name}</TableCell>
                        <TableCell>
                          {connectorTypeLabels[connector.type] || connector.type}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <StatusIcon
                              className={cn('h-4 w-4', statusColors[connector.status])}
                            />
                            <span className="text-sm">
                              {connector.status.replace('CONNECTOR_STATUS_', '')}
                            </span>
                          </div>
                        </TableCell>
                        <TableCell>{connector.docsAnalyzed}</TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {connector.lastSyncAt
                            ? new Date(connector.lastSyncAt).toLocaleString()
                            : 'Never'}
                        </TableCell>
                        <TableCell>
                          <div className="flex items-center gap-1">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => syncMutation.mutate(connector.id)}
                              disabled={syncMutation.isPending}
                            >
                              <RefreshCw className={cn('h-4 w-4', syncMutation.isPending && 'animate-spin')} />
                            </Button>
                            <Button variant="ghost" size="icon">
                              <Settings className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => setDeleteId(connector.id)}
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    )
                  })}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Delete Confirmation Dialog */}
        <Dialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete Connector</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this connector? All associated documents will also be deleted.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteId(null)}>
                Cancel
              </Button>
              <Button variant="destructive" onClick={handleDelete} disabled={deleteMutation.isPending}>
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
