import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { handleCallback } from './oidc'
import { authApi } from '@/api'
import { Loader2 } from 'lucide-react'

export function AuthCallback() {
  const navigate = useNavigate()
  const [status, setStatus] = useState('Completing sign in...')

  useEffect(() => {
    async function completeLogin() {
      try {
        // Step 1: Complete OIDC callback
        setStatus('Validating credentials...')
        await handleCallback()

        // Step 2: Sync user to local database
        setStatus('Syncing user profile...')
        const session = await authApi.createSession()
        console.log('User synced:', session.user.userName, session.message)

        // Step 3: Navigate to home
        navigate('/', { replace: true })
      } catch (error) {
        console.error('Auth callback error:', error)
        navigate('/login', { replace: true })
      }
    }

    completeLogin()
  }, [navigate])

  return (
    <div className="flex h-screen items-center justify-center">
      <div className="text-center">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground mx-auto mb-4" />
        <p className="text-muted-foreground">{status}</p>
      </div>
    </div>
  )
}
