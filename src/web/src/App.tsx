import { BrowserRouter, Routes, Route } from 'react-router-dom'
import { QueryClient, QueryClientProvider, QueryCache, MutationCache } from '@tanstack/react-query'
import { toast } from 'sonner'
import { ThemeProvider } from '@/components/theme-provider'
import { AuthProvider, AuthCallback, RequireAuth } from '@/auth'
import { TooltipProvider, Toaster } from '@/components/ui'
import { MainLayout } from '@/components/layout'
import { LoginPage } from '@/pages/Login'
import { ChatPage } from '@/features/chat/ChatPage'
import { DocumentsPage } from '@/features/documents/DocumentsPage'
import { ConnectorsPage } from '@/features/connectors/ConnectorsPage'
import { EmbeddingModelsPage } from '@/features/embedding-models/EmbeddingModelsPage'
import { LLMsPage } from '@/features/llms/LLMsPage'
import { AssistantsPage } from '@/features/assistants/AssistantsPage'
import { UsersPage } from '@/features/users/UsersPage'
import { SettingsPage } from '@/features/settings/SettingsPage'
import { ApiError } from '@/api/client'

function getErrorMessage(error: unknown): string {
  if (error instanceof ApiError) {
    if (error.status === 401) {
      return 'Session expired. Please log in again.'
    }
    if (error.status === 403) {
      return 'You do not have permission to perform this action.'
    }
    if (error.status === 404) {
      return 'The requested resource was not found.'
    }
    if (error.data && typeof error.data === 'object' && 'detail' in error.data) {
      return String(error.data.detail)
    }
    return `Error: ${error.status} ${error.statusText}`
  }
  if (error instanceof Error) {
    return error.message
  }
  return 'An unexpected error occurred'
}

const queryClient = new QueryClient({
  queryCache: new QueryCache({
    onError: (error) => {
      toast.error(getErrorMessage(error))
    },
  }),
  mutationCache: new MutationCache({
    onError: (error) => {
      toast.error(getErrorMessage(error))
    },
  }),
  defaultOptions: {
    queries: {
      staleTime: 1000 * 60 * 5, // 5 minutes
      retry: (failureCount, error) => {
        // Don't retry on 401/403/404
        if (error instanceof ApiError && [401, 403, 404].includes(error.status)) {
          return false
        }
        return failureCount < 1
      },
      refetchOnWindowFocus: false,
    },
  },
})

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider defaultTheme="system" storageKey="echomind-theme">
        <TooltipProvider>
          <BrowserRouter>
            <AuthProvider>
              <Routes>
                <Route path="/login" element={<LoginPage />} />
                <Route path="/auth/callback" element={<AuthCallback />} />
                <Route
                  element={
                    <RequireAuth>
                      <MainLayout />
                    </RequireAuth>
                  }
                >
                  <Route index element={<ChatPage />} />
                  <Route path="/chat/:sessionId" element={<ChatPage />} />
                  <Route path="/documents" element={<DocumentsPage />} />
                  <Route path="/connectors" element={<ConnectorsPage />} />
                  <Route path="/embedding-models" element={<EmbeddingModelsPage />} />
                  <Route path="/llms" element={<LLMsPage />} />
                  <Route path="/assistants" element={<AssistantsPage />} />
                  <Route path="/users" element={<UsersPage />} />
                  <Route path="/settings" element={<SettingsPage />} />
                </Route>
              </Routes>
            </AuthProvider>
          </BrowserRouter>
        </TooltipProvider>
        <Toaster position="top-right" richColors closeButton />
      </ThemeProvider>
    </QueryClientProvider>
  )
}
