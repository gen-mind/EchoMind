import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Cpu, Plus, Trash2, Play, Loader2, CheckCircle, Settings } from 'lucide-react'
import { llmsApi } from '@/api'
import type { LLMProvider } from '@/models'
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
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
} from '@/components/ui'

const providerLabels: Record<string, string> = {
  LLM_PROVIDER_TGI: 'TGI',
  LLM_PROVIDER_VLLM: 'vLLM',
  LLM_PROVIDER_OPENAI: 'OpenAI',
  LLM_PROVIDER_ANTHROPIC: 'Anthropic',
  LLM_PROVIDER_OLLAMA: 'Ollama',
}

export function LLMsPage() {
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [testingId, setTestingId] = useState<number | null>(null)
  const [newLLM, setNewLLM] = useState({
    name: '',
    provider: 'LLM_PROVIDER_OPENAI',
    modelId: '',
    endpoint: '',
    apiKey: '',
    maxTokens: 4096,
    temperature: 0.7,
    isDefault: false,
    isActive: true,
  })

  const { data: llmsData, isLoading } = useQuery({
    queryKey: ['llms'],
    queryFn: () => llmsApi.list(),
  })

  const llms = llmsData?.llms || []

  const createMutation = useMutation({
    mutationFn: llmsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llms'] })
      setIsCreateOpen(false)
      setNewLLM({
        name: '',
        provider: 'LLM_PROVIDER_OPENAI',
        modelId: '',
        endpoint: '',
        apiKey: '',
        maxTokens: 4096,
        temperature: 0.7,
        isDefault: false,
        isActive: true,
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: llmsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['llms'] })
      setDeleteId(null)
    },
  })

  const testMutation = useMutation({
    mutationFn: llmsApi.test,
    onSuccess: () => {
      setTestingId(null)
    },
    onError: () => {
      setTestingId(null)
    },
  })

  const handleCreate = () => {
    createMutation.mutate({
      name: newLLM.name,
      provider: newLLM.provider as LLMProvider,
      modelId: newLLM.modelId,
      endpoint: newLLM.endpoint,
      apiKey: newLLM.apiKey || undefined,
      maxTokens: newLLM.maxTokens,
      temperature: newLLM.temperature,
      isDefault: newLLM.isDefault,
      isActive: newLLM.isActive,
    })
  }

  const handleDelete = () => {
    if (deleteId) {
      deleteMutation.mutate(deleteId)
    }
  }

  const handleTest = (id: number) => {
    setTestingId(id)
    testMutation.mutate(id)
  }

  return (
    <div className="h-full overflow-auto">
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">LLM Configurations</h1>
            <p className="text-muted-foreground">
              Manage language model configurations for chat and generation
            </p>
          </div>
          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add LLM
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-lg">
              <DialogHeader>
                <DialogTitle>Add LLM Configuration</DialogTitle>
                <DialogDescription>
                  Configure a new language model for chat and generation.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
                <div className="space-y-2">
                  <Label>Name</Label>
                  <Input
                    value={newLLM.name}
                    onChange={(e) => setNewLLM({ ...newLLM, name: e.target.value })}
                    placeholder="GPT-4 Production"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Provider</Label>
                  <Select
                    value={newLLM.provider}
                    onValueChange={(v) => setNewLLM({ ...newLLM, provider: v })}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="LLM_PROVIDER_OPENAI">OpenAI</SelectItem>
                      <SelectItem value="LLM_PROVIDER_ANTHROPIC">Anthropic</SelectItem>
                      <SelectItem value="LLM_PROVIDER_TGI">TGI</SelectItem>
                      <SelectItem value="LLM_PROVIDER_VLLM">vLLM</SelectItem>
                      <SelectItem value="LLM_PROVIDER_OLLAMA">Ollama</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Model ID</Label>
                  <Input
                    value={newLLM.modelId}
                    onChange={(e) => setNewLLM({ ...newLLM, modelId: e.target.value })}
                    placeholder="gpt-4-turbo-preview"
                  />
                </div>
                <div className="space-y-2">
                  <Label>Endpoint</Label>
                  <Input
                    value={newLLM.endpoint}
                    onChange={(e) => setNewLLM({ ...newLLM, endpoint: e.target.value })}
                    placeholder="https://api.openai.com/v1"
                  />
                </div>
                <div className="space-y-2">
                  <Label>API Key</Label>
                  <Input
                    type="password"
                    value={newLLM.apiKey}
                    onChange={(e) => setNewLLM({ ...newLLM, apiKey: e.target.value })}
                    placeholder="sk-..."
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Max Tokens</Label>
                    <Input
                      type="number"
                      value={newLLM.maxTokens}
                      onChange={(e) => setNewLLM({ ...newLLM, maxTokens: Number(e.target.value) })}
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>Temperature</Label>
                    <Input
                      type="number"
                      step="0.1"
                      min="0"
                      max="2"
                      value={newLLM.temperature}
                      onChange={(e) => setNewLLM({ ...newLLM, temperature: Number(e.target.value) })}
                    />
                  </div>
                </div>
                <div className="flex items-center justify-between">
                  <Label>Set as Default</Label>
                  <Switch
                    checked={newLLM.isDefault}
                    onCheckedChange={(checked) => setNewLLM({ ...newLLM, isDefault: checked })}
                  />
                </div>
                <div className="flex items-center justify-between">
                  <Label>Active</Label>
                  <Switch
                    checked={newLLM.isActive}
                    onCheckedChange={(checked) => setNewLLM({ ...newLLM, isActive: checked })}
                  />
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={!newLLM.name || !newLLM.modelId || createMutation.isPending}
                >
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
            ) : llms.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Cpu className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No LLM configurations</p>
                <p className="text-sm">Add an LLM configuration to enable chat.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Provider</TableHead>
                    <TableHead>Model</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[180px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {llms.map((llm) => (
                    <TableRow key={llm.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <span className="font-medium">{llm.name}</span>
                          {llm.isDefault && (
                            <Badge variant="secondary" className="text-xs">Default</Badge>
                          )}
                        </div>
                      </TableCell>
                      <TableCell>{providerLabels[llm.provider] || llm.provider}</TableCell>
                      <TableCell className="font-mono text-sm">{llm.modelId}</TableCell>
                      <TableCell>
                        {llm.isActive ? (
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
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleTest(llm.id)}
                            disabled={testingId === llm.id}
                          >
                            {testingId === llm.id ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              <Play className="h-4 w-4" />
                            )}
                            <span className="ml-1">Test</span>
                          </Button>
                          <Button variant="ghost" size="icon">
                            <Settings className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteId(llm.id)}
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
              <DialogTitle>Delete LLM Configuration</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this LLM configuration?
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
