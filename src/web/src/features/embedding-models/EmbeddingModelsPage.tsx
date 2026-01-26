import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Layers, Plus, Trash2, CheckCircle, Loader2 } from 'lucide-react'
import { embeddingModelsApi } from '@/api'
import {
  Button,
  Badge,
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
} from '@/components/ui'

export function EmbeddingModelsPage() {
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [newModel, setNewModel] = useState({
    modelId: '',
    modelName: '',
    modelDimension: 768,
    endpoint: '',
  })

  const { data: modelsData, isLoading } = useQuery({
    queryKey: ['embedding-models'],
    queryFn: () => embeddingModelsApi.list(),
  })

  const models = modelsData?.models || []

  const createMutation = useMutation({
    mutationFn: embeddingModelsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedding-models'] })
      setIsCreateOpen(false)
      setNewModel({
        modelId: '',
        modelName: '',
        modelDimension: 768,
        endpoint: '',
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: embeddingModelsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedding-models'] })
      setDeleteId(null)
    },
  })

  const activateMutation = useMutation({
    mutationFn: embeddingModelsApi.activate,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['embedding-models'] })
    },
  })

  const handleCreate = () => {
    createMutation.mutate({
      modelId: newModel.modelId,
      modelName: newModel.modelName,
      modelDimension: newModel.modelDimension,
      endpoint: newModel.endpoint || undefined,
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
            <h1 className="text-2xl font-bold">Embedding Models</h1>
            <p className="text-muted-foreground">
              Configure embedding models for vector search
            </p>
          </div>
          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Model
              </Button>
            </DialogTrigger>
            <DialogContent>
              <DialogHeader>
                <DialogTitle>Add Embedding Model</DialogTitle>
                <DialogDescription>
                  Configure a new embedding model for generating document vectors.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4">
                <div className="space-y-2">
                  <Label>Model ID</Label>
                  <Input
                    value={newModel.modelId}
                    onChange={(e) => setNewModel({ ...newModel, modelId: e.target.value })}
                    placeholder="sentence-transformers/all-MiniLM-L6-v2"
                  />
                  <p className="text-xs text-muted-foreground">
                    HuggingFace model ID or custom model identifier
                  </p>
                </div>
                <div className="space-y-2">
                  <Label>Display Name</Label>
                  <Input
                    value={newModel.modelName}
                    onChange={(e) => setNewModel({ ...newModel, modelName: e.target.value })}
                    placeholder="MiniLM v2"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Vector Dimension</Label>
                  <Input
                    type="number"
                    value={newModel.modelDimension}
                    onChange={(e) =>
                      setNewModel({ ...newModel, modelDimension: Number(e.target.value) })
                    }
                    placeholder="768"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Endpoint (Optional)</Label>
                  <Input
                    value={newModel.endpoint}
                    onChange={(e) => setNewModel({ ...newModel, endpoint: e.target.value })}
                    placeholder="http://localhost:50051"
                  />
                  <p className="text-xs text-muted-foreground">
                    External embedding service URL (leave empty for local)
                  </p>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={!newModel.modelId || !newModel.modelName || createMutation.isPending}
                >
                  {createMutation.isPending ? 'Adding...' : 'Add Model'}
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
            ) : models.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Layers className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No embedding models configured</p>
                <p className="text-sm">Add an embedding model to enable vector search.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Model ID</TableHead>
                    <TableHead>Dimension</TableHead>
                    <TableHead>Endpoint</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[150px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {models.map((model) => (
                    <TableRow key={model.id}>
                      <TableCell className="font-medium">{model.modelName}</TableCell>
                      <TableCell className="font-mono text-sm">{model.modelId}</TableCell>
                      <TableCell>{model.modelDimension}</TableCell>
                      <TableCell className="text-muted-foreground text-sm">
                        {model.endpoint || 'Local'}
                      </TableCell>
                      <TableCell>
                        {model.isActive ? (
                          <Badge className="bg-green-500">
                            <CheckCircle className="h-3 w-3 mr-1" />
                            Active
                          </Badge>
                        ) : (
                          <Badge variant="secondary">Inactive</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          {!model.isActive && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => activateMutation.mutate(model.id)}
                              disabled={activateMutation.isPending}
                            >
                              {activateMutation.isPending ? 'Activating...' : 'Activate'}
                            </Button>
                          )}
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteId(model.id)}
                            disabled={model.isActive}
                          >
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </div>
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
            )}
          </CardContent>
        </Card>

        {/* Delete Confirmation Dialog */}
        <Dialog open={!!deleteId} onOpenChange={() => setDeleteId(null)}>
          <DialogContent>
            <DialogHeader>
              <DialogTitle>Delete Embedding Model</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this embedding model? This action cannot be undone.
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
