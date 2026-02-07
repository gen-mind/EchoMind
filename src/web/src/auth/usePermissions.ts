import { useMemo, useCallback } from 'react'
import { useAuth } from './AuthProvider'

/**
 * Authentik group names
 */
export const GROUPS = {
  ALLOWED: 'echomind-allowed',
  ADMINS: 'echomind-admins',
} as const

/**
 * Connector scopes matching backend RBAC
 */
export const SCOPES = {
  USER: 'user',
  TEAM: 'team',
  ORG: 'org',
} as const

export type ConnectorScope = (typeof SCOPES)[keyof typeof SCOPES]

/**
 * Permission levels for features.
 * - 'allowed': echomind-allowed and above
 * - 'admin': echomind-admins (highest privilege)
 */
type PermissionLevel = 'allowed' | 'admin'

/**
 * Feature permission configuration.
 * Maps feature names to the minimum group required.
 */
const FEATURE_PERMISSIONS: Record<string, PermissionLevel> = {
  // Available to all users (echomind-allowed and above)
  chat: 'allowed',
  documents: 'allowed',
  assistants: 'allowed',
  connectors: 'allowed',
  'connectors:view': 'allowed',
  'connectors:create:user': 'allowed',

  // Admin features (echomind-admins and above)
  users: 'admin',
  teams: 'admin',
  'teams:view': 'allowed', // View own teams
  'teams:create': 'admin',
  'teams:manage': 'admin',
  'connectors:manage': 'admin',
  'connectors:create:team': 'admin',

  // Admin features (infrastructure)
  'embedding-models': 'admin',
  llms: 'admin',
  portainer: 'admin',
  infrastructure: 'admin',
  'connectors:create:org': 'admin',
  'teams:delete': 'admin',
  'users:manage': 'admin',
}

/**
 * Map Authentik groups to permission level.
 * Higher level includes all permissions from lower levels.
 */
function getPermissionLevel(groups: string[]): PermissionLevel | null {
  if (groups.includes(GROUPS.ADMINS)) {
    return 'admin'
  }
  if (groups.includes(GROUPS.ALLOWED)) {
    return 'allowed'
  }
  return null
}

/**
 * Check if a permission level meets the required level.
 */
function meetsLevel(userLevel: PermissionLevel | null, requiredLevel: PermissionLevel): boolean {
  if (!userLevel) return false

  const levelHierarchy: PermissionLevel[] = ['allowed', 'admin']
  const userIndex = levelHierarchy.indexOf(userLevel)
  const requiredIndex = levelHierarchy.indexOf(requiredLevel)

  return userIndex >= requiredIndex
}

export interface UsePermissionsResult {
  /** User's permission level */
  level: PermissionLevel | null
  /** User's Authentik groups */
  groups: string[]
  /** User's ID (from token) */
  userId: number | null
  /** Check if user has a specific Authentik group */
  hasGroup: (group: string) => boolean
  /** Check if user has permission for a feature */
  can: (feature: string) => boolean
  /** Check if user is at least 'allowed' level */
  isAllowed: boolean
  /** Check if user is at least 'admin' level */
  isAdmin: boolean
  /** Check if user is 'superadmin' level */
  isSuperAdmin: boolean

  // Connector-specific permissions
  /** Check if user can create a connector with given scope */
  canCreateConnector: (scope: ConnectorScope, teamId?: number, userTeamIds?: number[]) => boolean
  /** Check if user can edit a connector */
  canEditConnector: (
    connector: { userId: number; scope: ConnectorScope; teamId?: number },
    userTeamIds?: number[],
    userTeamLeadIds?: number[]
  ) => boolean
  /** Check if user can delete a connector */
  canDeleteConnector: (
    connector: { userId: number; scope: ConnectorScope; teamId?: number },
    userTeamIds?: number[],
    userTeamLeadIds?: number[]
  ) => boolean
  /** Check if user can view a connector */
  canViewConnector: (
    connector: { userId: number; scope: ConnectorScope; teamId?: number },
    userTeamIds?: number[]
  ) => boolean

  // Team-specific permissions
  /** Check if user can create teams */
  canCreateTeam: boolean
  /** Check if user can manage a specific team */
  canManageTeam: (teamId: number, leaderId?: number, userTeamLeadIds?: number[]) => boolean
}

/**
 * Hook to check user permissions based on Authentik groups.
 *
 * Implements RBAC rules defined in docs/rbac.md.
 *
 * @example
 * ```tsx
 * function ConnectorPage() {
 *   const { canCreateConnector, canEditConnector, isAdmin } = usePermissions()
 *
 *   return (
 *     <div>
 *       {canCreateConnector('user') && <CreatePersonalConnectorButton />}
 *       {canCreateConnector('team', teamId, userTeamIds) && <CreateTeamConnectorButton />}
 *       {canCreateConnector('org') && <CreateOrgConnectorButton />}
 *     </div>
 *   )
 * }
 * ```
 *
 * @example
 * ```tsx
 * function AdminPanel() {
 *   const { isAdmin, isSuperAdmin, can } = usePermissions()
 *
 *   return (
 *     <div>
 *       {can('users') && <UsersSection />}
 *       {can('embedding-models') && <EmbeddingsSection />}
 *       {isSuperAdmin && <InfrastructureSection />}
 *     </div>
 *   )
 * }
 * ```
 */
export function usePermissions(): UsePermissionsResult {
  const { user } = useAuth()

  // Extract user info from OIDC token
  const groups: string[] = useMemo(
    () => (user?.profile?.groups as string[]) || [],
    [user]
  )

  const userId: number | null = useMemo(() => {
    // user.profile.sub is the user ID from Authentik
    const sub = user?.profile?.sub
    if (!sub) return null
    // Try to parse as number, fallback to null
    const parsed = parseInt(sub, 10)
    return isNaN(parsed) ? null : parsed
  }, [user])

  const level = useMemo(() => getPermissionLevel(groups), [groups])

  const isAllowed = level !== null
  const isAdmin = meetsLevel(level, 'admin')
  const isSuperAdmin = isAdmin // Backward compat alias — superadmin collapsed into admin

  // Basic permission check
  const can = useCallback(
    (feature: string): boolean => {
      const requiredLevel = FEATURE_PERMISSIONS[feature]
      if (!requiredLevel) {
        // Unknown feature - deny by default
        console.warn(`Unknown permission feature: ${feature}`)
        return false
      }
      return meetsLevel(level, requiredLevel)
    },
    [level]
  )

  const hasGroup = useCallback(
    (group: string): boolean => groups.includes(group),
    [groups]
  )

  // Connector permissions
  const canCreateConnector = useCallback(
    (scope: ConnectorScope, teamId?: number, userTeamIds?: number[]): boolean => {
      if (isSuperAdmin) return true

      if (scope === SCOPES.USER) {
        return isAllowed
      }

      if (scope === SCOPES.TEAM) {
        // Must be admin AND member of the team
        if (!isAdmin) return false
        if (!teamId || !userTeamIds) return false
        return userTeamIds.includes(teamId)
      }

      if (scope === SCOPES.ORG) {
        return isSuperAdmin
      }

      return false
    },
    [isAllowed, isAdmin, isSuperAdmin]
  )

  const canViewConnector = useCallback(
    (
      connector: { userId: number; scope: ConnectorScope; teamId?: number },
      userTeamIds?: number[]
    ): boolean => {
      if (isSuperAdmin) return true

      const { userId: connectorUserId, scope, teamId } = connector

      if (scope === SCOPES.USER) {
        // Owner only
        return connectorUserId === userId
      }

      if (scope === SCOPES.TEAM) {
        // Team members
        if (!teamId || !userTeamIds) return false
        return userTeamIds.includes(teamId)
      }

      if (scope === SCOPES.ORG) {
        // All allowed users
        return isAllowed
      }

      return false
    },
    [userId, isAllowed, isSuperAdmin]
  )

  const canEditConnector = useCallback(
    (
      connector: { userId: number; scope: ConnectorScope; teamId?: number },
      userTeamIds?: number[],
      userTeamLeadIds?: number[]
    ): boolean => {
      if (isSuperAdmin) return true

      const { userId: connectorUserId, scope, teamId } = connector

      if (scope === SCOPES.USER) {
        // Owner only
        return connectorUserId === userId
      }

      if (scope === SCOPES.TEAM) {
        // Team lead or admin who is member
        if (!teamId) return false

        // Check if user is team lead
        if (userTeamLeadIds?.includes(teamId)) return true

        // Admins who are team members can edit
        if (isAdmin && userTeamIds?.includes(teamId)) return true

        return false
      }

      if (scope === SCOPES.ORG) {
        // Superadmin only (already checked above)
        return false
      }

      return false
    },
    [userId, isAdmin, isSuperAdmin]
  )

  // Delete uses same rules as edit
  const canDeleteConnector = canEditConnector

  // Team permissions
  const canCreateTeam = isAdmin

  const canManageTeam = useCallback(
    (teamId: number, leaderId?: number, userTeamLeadIds?: number[]): boolean => {
      if (isSuperAdmin) return true
      if (isAdmin) return true // Admins can manage any team

      // Team leader can manage
      if (leaderId === userId) return true

      // Check if user is lead of this team
      if (userTeamLeadIds?.includes(teamId)) return true

      return false
    },
    [userId, isAdmin, isSuperAdmin]
  )

  return useMemo(
    () => ({
      level,
      groups,
      userId,
      hasGroup,
      can,
      isAllowed,
      isAdmin,
      isSuperAdmin,
      canCreateConnector,
      canViewConnector,
      canEditConnector,
      canDeleteConnector,
      canCreateTeam,
      canManageTeam,
    }),
    [
      level,
      groups,
      userId,
      hasGroup,
      can,
      isAllowed,
      isAdmin,
      isSuperAdmin,
      canCreateConnector,
      canViewConnector,
      canEditConnector,
      canDeleteConnector,
      canManageTeam,
    ]
  )
}
