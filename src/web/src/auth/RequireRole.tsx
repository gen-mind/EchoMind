import { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { usePermissions } from './usePermissions'

interface RequireRoleProps {
  children: ReactNode
  /** Feature permission required to access this content */
  feature?: string
  /** Minimum level required: 'allowed' or 'admin' */
  level?: 'allowed' | 'admin'
  /** Where to redirect if access is denied (default: /) */
  redirectTo?: string
  /** Content to show if access is denied (instead of redirect) */
  fallback?: ReactNode
}

/**
 * Component to protect routes or content based on user permission level.
 *
 * @example
 * ```tsx
 * // Protect a route by feature
 * <Route
 *   path="/users"
 *   element={
 *     <RequireRole feature="users">
 *       <UsersPage />
 *     </RequireRole>
 *   }
 * />
 *
 * // Protect by level
 * <RequireRole level="admin">
 *   <InfrastructurePage />
 * </RequireRole>
 *
 * // Protect content with fallback
 * <RequireRole feature="llms" fallback={<AccessDenied />}>
 *   <LLMConfig />
 * </RequireRole>
 * ```
 */
export function RequireRole({
  children,
  feature,
  level,
  redirectTo = '/',
  fallback,
}: RequireRoleProps) {
  const { can, isAllowed, isAdmin, isSuperAdmin } = usePermissions()

  // Check feature permission if specified
  if (feature && !can(feature)) {
    if (fallback) return <>{fallback}</>
    return <Navigate to={redirectTo} replace />
  }

  // Check level if specified
  if (level) {
    let hasAccess = false
    switch (level) {
      case 'allowed':
        hasAccess = isAllowed
        break
      case 'admin':
        hasAccess = isAdmin
        break
    }
    if (!hasAccess) {
      if (fallback) return <>{fallback}</>
      return <Navigate to={redirectTo} replace />
    }
  }

  return <>{children}</>
}
