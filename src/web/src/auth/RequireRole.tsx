import { ReactNode } from 'react'
import { Navigate } from 'react-router-dom'
import { usePermissions } from './usePermissions'

interface RequireRoleProps {
  children: ReactNode
  /** Role required to access this content */
  role?: string
  /** Permission required to access this content */
  permission?: string
  /** Where to redirect if access is denied (default: /) */
  redirectTo?: string
  /** Content to show if access is denied (instead of redirect) */
  fallback?: ReactNode
}

/**
 * Component to protect routes or content based on user role/permission.
 *
 * @example
 * ```tsx
 * // Protect a route
 * <Route
 *   path="/users"
 *   element={
 *     <RequireRole role="admin">
 *       <UsersPage />
 *     </RequireRole>
 *   }
 * />
 *
 * // Protect content with fallback
 * <RequireRole permission="users" fallback={<AccessDenied />}>
 *   <UsersList />
 * </RequireRole>
 * ```
 */
export function RequireRole({
  children,
  role,
  permission,
  redirectTo = '/',
  fallback,
}: RequireRoleProps) {
  const { hasRole, can } = usePermissions()

  // Check role if specified
  if (role && !hasRole(role)) {
    if (fallback) return <>{fallback}</>
    return <Navigate to={redirectTo} replace />
  }

  // Check permission if specified
  if (permission && !can(permission)) {
    if (fallback) return <>{fallback}</>
    return <Navigate to={redirectTo} replace />
  }

  return <>{children}</>
}
