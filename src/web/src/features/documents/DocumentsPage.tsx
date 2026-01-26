import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { FileText, Search, Trash2, ExternalLink, Loader2 } from 'lucide-react'
import { documentsApi, connectorsApi } from '@/api'
import type { DocumentStatus } from '@/models'
import {
  Button,
  Input,
  Badge,
  Card,
  CardContent,
  CardHeader,
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from '@/components/ui'
import { cn } from '@/lib/utils'

const statusColors: Record<string, string> = {
  DOCUMENT_STATUS_PENDING: 'bg-yellow-500',
  DOCUMENT_STATUS_PROCESSING: 'bg-blue-500',
  DOCUMENT_STATUS_COMPLETED: 'bg-green-500',
  DOCUMENT_STATUS_FAILED: 'bg-red-500',
}

const statusLabels: Record<string, string> = {
  DOCUMENT_STATUS_PENDING: 'Pending',
  DOCUMENT_STATUS_PROCESSING: 'Processing',
  DOCUMENT_STATUS_COMPLETED: 'Completed',
  DOCUMENT_STATUS_FAILED: 'Failed',
}

export function DocumentsPage() {
  const queryClient = useQueryClient()
  const [searchQuery, setSearchQuery] = useState('')
  const [statusFilter, setStatusFilter] = useState<string>('all')
  const [connectorFilter, setConnectorFilter] = useState<string>('all')
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [page, setPage] = useState(1)
  const limit = 20

  const { data: connectorsData } = useQuery({
    queryKey: ['connectors'],
    queryFn: () => connectorsApi.list(),
  })

  const connectors = connectorsData?.connectors || []

  const { data: documentsData, isLoading } = useQuery({
    queryKey: ['documents', { page, limit, status: statusFilter, connector_id: connectorFilter }],
    queryFn: () =>
      documentsApi.list({
        page,
        limit,
        status: statusFilter !== 'all' ? (statusFilter as DocumentStatus) : undefined,
        connector_id: connectorFilter !== 'all' ? Number(connectorFilter) : undefined,
      }),
  })

  const documents = documentsData?.documents || []
  const pagination = documentsData?.pagination

  const deleteMutation = useMutation({
    mutationFn: documentsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['documents'] })
      setDeleteId(null)
    },
  })

  const handleDelete = () => {
    if (deleteId) {
      deleteMutation.mutate(deleteId)
    }
  }

  const getConnectorName = (connectorId: number) => {
    const connector = connectors.find((c) => c.id === connectorId)
    return connector?.name || `Connector ${connectorId}`
  }

  return (
    <div className="h-full overflow-auto">
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Documents</h1>
            <p className="text-muted-foreground">
              View and manage documents from your connectors
            </p>
          </div>
        </div>

        <Card>
          <CardHeader>
            <div className="flex flex-col sm:flex-row gap-4">
              <div className="relative flex-1">
                <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                <Input
                  placeholder="Search documents..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="pl-9"
                />
              </div>
              <Select value={statusFilter} onValueChange={setStatusFilter}>
                <SelectTrigger className="w-[150px]">
                  <SelectValue placeholder="Status" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Status</SelectItem>
                  <SelectItem value="DOCUMENT_STATUS_PENDING">Pending</SelectItem>
                  <SelectItem value="DOCUMENT_STATUS_PROCESSING">Processing</SelectItem>
                  <SelectItem value="DOCUMENT_STATUS_COMPLETED">Completed</SelectItem>
                  <SelectItem value="DOCUMENT_STATUS_FAILED">Failed</SelectItem>
                </SelectContent>
              </Select>
              <Select value={connectorFilter} onValueChange={setConnectorFilter}>
                <SelectTrigger className="w-[180px]">
                  <SelectValue placeholder="Connector" />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">All Connectors</SelectItem>
                  {connectors.map((connector) => (
                    <SelectItem key={connector.id} value={connector.id.toString()}>
                      {connector.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardHeader>
          <CardContent>
            {isLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
              </div>
            ) : documents.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <FileText className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No documents found</p>
              </div>
            ) : (
              <>
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Title</TableHead>
                      <TableHead>Connector</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Chunks</TableHead>
                      <TableHead>Updated</TableHead>
                      <TableHead className="w-[100px]">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {documents.map((doc) => (
                      <TableRow key={doc.id}>
                        <TableCell>
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 text-muted-foreground" />
                            <div className="min-w-0">
                              <p className="font-medium truncate max-w-[300px]">
                                {doc.title || doc.url || `Document ${doc.id}`}
                              </p>
                              {doc.url && (
                                <a
                                  href={doc.originalUrl || doc.url}
                                  target="_blank"
                                  rel="noopener noreferrer"
                                  className="text-xs text-muted-foreground hover:underline flex items-center gap-1"
                                >
                                  <ExternalLink className="h-3 w-3" />
                                  View source
                                </a>
                              )}
                            </div>
                          </div>
                        </TableCell>
                        <TableCell>{getConnectorName(doc.connectorId)}</TableCell>
                        <TableCell>
                          <Badge
                            variant="secondary"
                            className={cn(
                              'text-white',
                              statusColors[doc.status] || 'bg-gray-500'
                            )}
                          >
                            {statusLabels[doc.status] || doc.status}
                          </Badge>
                        </TableCell>
                        <TableCell>{doc.chunkCount}</TableCell>
                        <TableCell className="text-muted-foreground text-sm">
                          {doc.lastUpdate
                            ? new Date(doc.lastUpdate).toLocaleDateString()
                            : '-'}
                        </TableCell>
                        <TableCell>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteId(doc.id)}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>

                {/* Pagination */}
                {pagination && pagination.pages > 1 && (
                  <div className="flex items-center justify-between mt-4">
                    <p className="text-sm text-muted-foreground">
                      Showing {documents.length} of {pagination.total} documents
                    </p>
                    <div className="flex gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={page === 1}
                        onClick={() => setPage((p) => p - 1)}
                      >
                        Previous
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={page >= pagination.pages}
                        onClick={() => setPage((p) => p + 1)}
                      >
                        Next
                      </Button>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* Delete Confirmation Dialog */}
        <Dialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete Document</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this document? This action cannot be undone.
              </DialogDescription>
            </DialogHeader>
            <DialogFooter>
              <Button variant="outline" onClick={() => setDeleteId(null)}>
                Cancel
              </Button>
              <Button
                variant="destructive"
                onClick={handleDelete}
                disabled={deleteMutation.isPending}
              >
                {deleteMutation.isPending ? 'Deleting...' : 'Delete'}
              </Button>
            </DialogFooter>
          </DialogContent>
        </Dialog>
      </div>
    </div>
  )
}
