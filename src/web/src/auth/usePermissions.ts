import { useMemo } from 'react'
import { useAuth } from './AuthProvider'

/**
 * Permission configuration mapping roles to features.
 * Add new roles/permissions here as needed.
 */
const ROLE_PERMISSIONS: Record<string, string[]> = {
  admin: ['users', 'settings', 'llms', 'assistants', 'connectors', 'documents', 'embedding-models', 'chat'],
  user: ['chat', 'documents', 'assistants'],
}

/**
 * Map Authentik groups to application roles.
 * The group "echomind-admins" grants the "admin" role.
 */
function mapGroupsToRoles(groups: string[]): string[] {
  const roles: string[] = ['user'] // Everyone gets base user role

  if (groups.includes('echomind-admins')) {
    roles.push('admin')
  }

  return roles
}

/**
 * Get all permissions for a set of roles.
 */
function getPermissionsForRoles(roles: string[]): Set<string> {
  const permissions = new Set<string>()

  for (const role of roles) {
    const rolePerms = ROLE_PERMISSIONS[role]
    if (rolePerms) {
      rolePerms.forEach((p) => permissions.add(p))
    }
  }

  return permissions
}

export interface UsePermissionsResult {
  /** User's roles (e.g., ['user', 'admin']) */
  roles: string[]
  /** User's Authentik groups */
  groups: string[]
  /** Check if user has a specific role */
  hasRole: (role: string) => boolean
  /** Check if user has permission for a feature */
  can: (permission: string) => boolean
  /** Check if user is an admin */
  isAdmin: boolean
}

/**
 * Hook to check user roles and permissions.
 *
 * @example
 * ```tsx
 * function AdminPanel() {
 *   const { isAdmin, can } = usePermissions()
 *
 *   if (!isAdmin) return null
 *
 *   return (
 *     <div>
 *       {can('users') && <UsersSection />}
 *     </div>
 *   )
 * }
 * ```
 */
export function usePermissions(): UsePermissionsResult {
  const { user } = useAuth()

  return useMemo(() => {
    // Extract groups from OIDC token
    const groups: string[] = (user?.profile?.groups as string[]) || []

    // Map groups to roles
    const roles = mapGroupsToRoles(groups)

    // Get all permissions for the user's roles
    const permissions = getPermissionsForRoles(roles)

    return {
      roles,
      groups,
      hasRole: (role: string) => roles.includes(role),
      can: (permission: string) => permissions.has(permission),
      isAdmin: roles.includes('admin'),
    }
  }, [user])
}
