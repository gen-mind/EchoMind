import { UserManager, WebStorageStateStore, User } from 'oidc-client-ts'

// Validate required environment variables
const requiredEnvVars = [
  'VITE_OIDC_AUTHORITY',
  'VITE_OIDC_CLIENT_ID',
  'VITE_OIDC_REDIRECT_URI',
] as const

const missingVars = requiredEnvVars.filter((key) => !import.meta.env[key])
if (missingVars.length > 0) {
  console.error(
    `Missing required environment variables: ${missingVars.join(', ')}\n` +
    'Please configure these in your .env file. See .env.example for reference.'
  )
}

// Debug: Log env values
console.log('OIDC Config from env:', {
  authority: import.meta.env.VITE_OIDC_AUTHORITY,
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID,
})

const oidcConfig = {
  authority: import.meta.env.VITE_OIDC_AUTHORITY || '',
  client_id: import.meta.env.VITE_OIDC_CLIENT_ID || '',
  redirect_uri: import.meta.env.VITE_OIDC_REDIRECT_URI || `${window.location.origin}/auth/callback`,
  post_logout_redirect_uri: import.meta.env.VITE_OIDC_POST_LOGOUT_REDIRECT_URI || window.location.origin,
  response_type: 'code',
  scope: import.meta.env.VITE_OIDC_SCOPE || 'openid profile email offline_access',
  // Enable automatic silent token renewal
  automaticSilentRenew: true,
  // Renew token 60 seconds before expiry
  accessTokenExpiringNotificationTimeInSeconds: 60,
  // Use localStorage to persist session across tabs
  userStore: new WebStorageStateStore({ store: window.localStorage }),
}

let userManager: UserManager | null = null

export function getUserManager(): UserManager {
  if (!userManager) {
    userManager = new UserManager(oidcConfig)
  }
  return userManager
}

export async function getUser(): Promise<User | null> {
  const um = getUserManager()
  return await um.getUser()
}

export async function login(): Promise<void> {
  const um = getUserManager()
  await um.signinRedirect()
}

export async function logout(): Promise<void> {
  const um = getUserManager()
  await um.signoutRedirect()
}

export async function handleCallback(): Promise<User> {
  const um = getUserManager()
  return await um.signinRedirectCallback()
}

export async function silentRenew(): Promise<User | null> {
  const um = getUserManager()
  try {
    return await um.signinSilent()
  } catch {
    return null
  }
}

export function getAccessToken(user: User | null): string | null {
  return user?.access_token ?? null
}
