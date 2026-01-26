import { useState } from 'react'
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query'
import { Bot, Plus, Trash2, Settings, Loader2, Star } from 'lucide-react'
import { assistantsApi, llmsApi } from '@/api'
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
  Textarea,
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
  Switch,
} from '@/components/ui'

export function AssistantsPage() {
  const queryClient = useQueryClient()
  const [isCreateOpen, setIsCreateOpen] = useState(false)
  const [deleteId, setDeleteId] = useState<number | null>(null)
  const [newAssistant, setNewAssistant] = useState({
    name: '',
    description: '',
    llmId: '',
    systemPrompt: '',
    taskPrompt: '',
    starterMessages: '',
    isDefault: false,
    isVisible: true,
    displayPriority: 0,
  })

  const { data: assistantsData, isLoading } = useQuery({
    queryKey: ['assistants'],
    queryFn: () => assistantsApi.list(),
  })

  const { data: llmsData } = useQuery({
    queryKey: ['llms'],
    queryFn: () => llmsApi.list(),
  })

  const assistants = assistantsData?.assistants || []
  const llms = llmsData?.llms || []

  const createMutation = useMutation({
    mutationFn: assistantsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assistants'] })
      setIsCreateOpen(false)
      setNewAssistant({
        name: '',
        description: '',
        llmId: '',
        systemPrompt: '',
        taskPrompt: '',
        starterMessages: '',
        isDefault: false,
        isVisible: true,
        displayPriority: 0,
      })
    },
  })

  const deleteMutation = useMutation({
    mutationFn: assistantsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['assistants'] })
      setDeleteId(null)
    },
  })

  const handleCreate = () => {
    createMutation.mutate({
      name: newAssistant.name,
      description: newAssistant.description,
      llmId: newAssistant.llmId ? Number(newAssistant.llmId) : undefined,
      systemPrompt: newAssistant.systemPrompt,
      taskPrompt: newAssistant.taskPrompt,
      starterMessages: newAssistant.starterMessages
        .split('\n')
        .map((s) => s.trim())
        .filter(Boolean),
      isDefault: newAssistant.isDefault,
      isVisible: newAssistant.isVisible,
      displayPriority: newAssistant.displayPriority,
    })
  }

  const handleDelete = () => {
    if (deleteId) {
      deleteMutation.mutate(deleteId)
    }
  }

  const getLLMName = (llmId?: number) => {
    if (!llmId) return 'Default'
    const llm = llms.find((l) => l.id === llmId)
    return llm?.name || `LLM ${llmId}`
  }

  return (
    <div className="h-full overflow-auto">
      <div className="p-6 max-w-6xl mx-auto space-y-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Assistants</h1>
            <p className="text-muted-foreground">
              Configure AI assistant personalities and behaviors
            </p>
          </div>
          <Dialog open={isCreateOpen} onOpenChange={setIsCreateOpen}>
            <DialogTrigger asChild>
              <Button>
                <Plus className="h-4 w-4 mr-2" />
                Add Assistant
              </Button>
            </DialogTrigger>
            <DialogContent className="max-w-2xl">
              <DialogHeader>
                <DialogTitle>Create Assistant</DialogTitle>
                <DialogDescription>
                  Configure a new AI assistant with custom personality and prompts.
                </DialogDescription>
              </DialogHeader>
              <div className="space-y-4 py-4 max-h-[60vh] overflow-y-auto">
                <div className="grid grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label>Name</Label>
                    <Input
                      value={newAssistant.name}
                      onChange={(e) => setNewAssistant({ ...newAssistant, name: e.target.value })}
                      placeholder="General Assistant"
                    />
                  </div>
                  <div className="space-y-2">
                    <Label>LLM</Label>
                    <Select
                      value={newAssistant.llmId}
                      onValueChange={(v) => setNewAssistant({ ...newAssistant, llmId: v })}
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Select LLM" />
                      </SelectTrigger>
                      <SelectContent>
                        {llms.map((llm) => (
                          <SelectItem key={llm.id} value={llm.id.toString()}>
                            {llm.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label>Description</Label>
                  <Input
                    value={newAssistant.description}
                    onChange={(e) => setNewAssistant({ ...newAssistant, description: e.target.value })}
                    placeholder="A helpful assistant for general questions"
                  />
                </div>
                <div className="space-y-2">
                  <Label>System Prompt</Label>
                  <Textarea
                    value={newAssistant.systemPrompt}
                    onChange={(e) => setNewAssistant({ ...newAssistant, systemPrompt: e.target.value })}
                    placeholder="You are a helpful assistant..."
                    rows={4}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Task Prompt</Label>
                  <Textarea
                    value={newAssistant.taskPrompt}
                    onChange={(e) => setNewAssistant({ ...newAssistant, taskPrompt: e.target.value })}
                    placeholder="Answer the user's question based on the provided context..."
                    rows={4}
                  />
                </div>
                <div className="space-y-2">
                  <Label>Starter Messages (one per line)</Label>
                  <Textarea
                    value={newAssistant.starterMessages}
                    onChange={(e) =>
                      setNewAssistant({ ...newAssistant, starterMessages: e.target.value })
                    }
                    placeholder="What can you help me with?&#10;Tell me about the company policies&#10;How do I submit a request?"
                    rows={3}
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div className="flex items-center justify-between">
                    <Label>Default Assistant</Label>
                    <Switch
                      checked={newAssistant.isDefault}
                      onCheckedChange={(checked) =>
                        setNewAssistant({ ...newAssistant, isDefault: checked })
                      }
                    />
                  </div>
                  <div className="flex items-center justify-between">
                    <Label>Visible to Users</Label>
                    <Switch
                      checked={newAssistant.isVisible}
                      onCheckedChange={(checked) =>
                        setNewAssistant({ ...newAssistant, isVisible: checked })
                      }
                    />
                  </div>
                </div>
              </div>
              <DialogFooter>
                <Button variant="outline" onClick={() => setIsCreateOpen(false)}>
                  Cancel
                </Button>
                <Button
                  onClick={handleCreate}
                  disabled={!newAssistant.name || createMutation.isPending}
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
            ) : assistants.length === 0 ? (
              <div className="text-center py-8 text-muted-foreground">
                <Bot className="h-12 w-12 mx-auto mb-4 opacity-50" />
                <p>No assistants configured</p>
                <p className="text-sm">Create an assistant to customize chat behavior.</p>
              </div>
            ) : (
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Name</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>LLM</TableHead>
                    <TableHead>Status</TableHead>
                    <TableHead className="w-[120px]">Actions</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {assistants.map((assistant) => (
                    <TableRow key={assistant.id}>
                      <TableCell>
                        <div className="flex items-center gap-2">
                          <Bot className="h-4 w-4 text-muted-foreground" />
                          <span className="font-medium">{assistant.name}</span>
                          {assistant.isDefault && (
                            <Star className="h-4 w-4 text-yellow-500 fill-yellow-500" />
                          )}
                        </div>
                      </TableCell>
                      <TableCell className="max-w-[300px] truncate text-muted-foreground">
                        {assistant.description}
                      </TableCell>
                      <TableCell>{getLLMName(assistant.llmId)}</TableCell>
                      <TableCell>
                        {assistant.isVisible ? (
                          <Badge className="bg-green-500">Visible</Badge>
                        ) : (
                          <Badge variant="secondary">Hidden</Badge>
                        )}
                      </TableCell>
                      <TableCell>
                        <div className="flex items-center gap-1">
                          <Button variant="ghost" size="icon">
                            <Settings className="h-4 w-4" />
                          </Button>
                          <Button
                            variant="ghost"
                            size="icon"
                            onClick={() => setDeleteId(assistant.id)}
                            disabled={assistant.isDefault}
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
              <DialogTitle>Delete Assistant</DialogTitle>
              <DialogDescription>
                Are you sure you want to delete this assistant? This action cannot be undone.
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
