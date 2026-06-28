const API_BASE = import.meta.env.VITE_API_BASE || '';

function getToken(): string | null {
  return localStorage.getItem('aibond_token');
}

async function request(url: string, options: RequestInit = {}) {
  const token = getToken();
  const headers: Record<string, string> = {
    'Content-Type': 'application/json',
    ...(options.headers as Record<string, string>),
  };
  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  const res = await fetch(`${API_BASE}${url}`, { ...options, headers });
  if (!res.ok) {
    const error = await res.json().catch(() => ({ detail: 'Request failed' }));
    // Handle rate limiting
    if (res.status === 429) {
      throw new Error(error.detail || '请求过于频繁，请稍后再试');
    }
    // Handle auth errors
    if (res.status === 401) {
      // Clear invalid token
      localStorage.removeItem('aibond_token');
      localStorage.removeItem('aibond_user');
      window.location.href = '/login';
      throw new Error('登录已过期，请重新登录');
    }
    throw new Error(error.detail || 'Request failed');
  }
  return res.json();
}

export const api = {
  // Auth
  register: (username: string, password: string, email?: string) =>
    request('/api/auth/register', { method: 'POST', body: JSON.stringify({ username, password, email }) }),
  login: (username: string, password: string) =>
    request('/api/auth/login', { method: 'POST', body: JSON.stringify({ username, password }) }),
  getMe: (token: string) =>
    request('/api/auth/me', { method: 'POST', body: JSON.stringify({ token }) }),

  // Agents
  registerAgent: (name: string, skills?: string[], callbackUrl?: string) =>
    request('/api/agents/register', { method: 'POST', body: JSON.stringify({ name, skills, callback_url: callbackUrl }) }),
  listAgents: (status?: string) =>
    request(`/api/agents/${status ? `?status=${status}` : ''}`),
  getAgent: (id: string) =>
    request(`/api/agents/${id}`),
  // Agent 一键注册
  createAgentToken: (name: string) =>
    request('/api/agents/create-token', { method: 'POST', body: JSON.stringify({ name }) }),
  // 获取可用Agent列表（下拉选择用）
  listAvailableAgents: () =>
    request('/api/agents/available'),

  // Groups
  createGroup: (name: string, description: string, ownerId: string) =>
    request('/api/groups/', { method: 'POST', body: JSON.stringify({ name, description, owner_id: ownerId }) }),
  listGroups: () =>
    request('/api/groups/'),
  getGroup: (id: string) =>
    request(`/api/groups/${id}`),
  getGroupDetail: (id: string) =>
    request(`/api/groups/${id}`),
  addMember: (groupId: string, memberType: string, memberId: string, role?: string) =>
    request(`/api/groups/${groupId}/members`, { method: 'POST', body: JSON.stringify({ member_type: memberType, member_id: memberId, role }) }),
  addGroupWithAgent: (groupId: string, agentId: string, role?: string) =>
    request(`/api/groups/${groupId}/members`, { method: 'POST', body: JSON.stringify({ member_type: 'agent', member_id: agentId, role: role || 'member' }) }),
  addGroupWithUser: (groupId: string, userId: string, role?: string) =>
    request(`/api/groups/${groupId}/members`, { method: 'POST', body: JSON.stringify({ member_type: 'user', member_id: userId, role: role || 'member' }) }),
  getMessages: (groupId: string, limit?: number, offset?: number) =>
    request(`/api/groups/${groupId}/messages?limit=${limit || 50}&offset=${offset || 0}`),

  // Messages
  sendMessage: (groupId: string, senderType: string, senderId: string, content: string, msgType?: string, metadata?: any) =>
    request('/api/messages/', { method: 'POST', body: JSON.stringify({ group_id: groupId, sender_type: senderType, sender_id: senderId, content, msg_type: msgType || 'text', metadata }) }),

  // Sessions
  createSession: (groupId: string, title: string, description: string, assignerType: string, assignerId: string, assigneeIds: string[], priority?: string) =>
    request('/api/sessions/', { method: 'POST', body: JSON.stringify({ group_id: groupId, title, description, assigner_type: assignerType, assigner_id: assignerId, assignee_ids: assigneeIds, priority: priority || 'medium' }) }),
  listSessions: (groupId: string) =>
    request(`/api/sessions/?group_id=${groupId}`),
  getSession: (id: string) =>
    request(`/api/sessions/${id}`),
  sendSessionMessage: (sessionId: string, senderType: string, senderId: string, content: string, msgType?: string) =>
    request(`/api/sessions/${sessionId}/messages`, { method: 'POST', body: JSON.stringify({ sender_type: senderType, sender_id: senderId, content, msg_type: msgType || 'text' }) }),
  updateSessionStatus: (sessionId: string, status: string, result?: any, summary?: string) =>
    request(`/api/sessions/${sessionId}/status`, { method: 'POST', body: JSON.stringify({ status, result, summary }) }),

  // Files
  uploadFile: (formData: FormData) =>
    fetch(`${API_BASE}/api/files/upload`, { method: 'POST', body: formData, headers: { 'Authorization': `Bearer ${getToken()}` } }).then(r => r.json()),
  listFiles: (groupId?: string, sessionId?: string) =>
    request(`/api/files/list?${groupId ? 'group_id=' + groupId : ''}${sessionId ? '&session_id=' + sessionId : ''}`),
  downloadFile: (fileId: string) =>
    `${API_BASE}/api/files/${fileId}`,

  // Agent tasks
  getAgentTasks: (agentId: string) =>
    request(`/api/agents/${agentId}/tasks`),

  // Workflows
  createWorkflow: (name: string, description: string, ownerId: string, definition?: any, triggerType?: string) =>
    request('/api/workflows/', { method: 'POST', body: JSON.stringify({ name, description, owner_id: ownerId, definition, trigger_type: triggerType }) }),
  listWorkflows: () =>
    request('/api/workflows/'),
  getWorkflow: (id: string) =>
    request(`/api/workflows/${id}`),
  updateWorkflowDefinition: (id: string, definition: any) =>
    request(`/api/workflows/${id}/definition`, { method: 'PUT', body: JSON.stringify({ definition }) }),
  runWorkflow: (id: string) =>
    request(`/api/workflows/${id}/run`, { method: 'POST' }),

  // ===== 新增 API =====

  // Audit Log
  listAudit: (params?: { actor_type?: string; action?: string; offset?: number; limit?: number }) =>
    request(`/api/audit/?${params ? new URLSearchParams(params as Record<string, string>).toString() : ''}`),
  getAuditStats: () =>
    request('/api/audit/stats'),
  exportAuditCSV: (params?: { actor_type?: string; action?: string }) =>
    fetch(`${API_BASE}/api/audit/export?${params ? new URLSearchParams(params as Record<string, string>).toString() : ''}`, {
      headers: { 'Authorization': `Bearer ${getToken()}` },
    }).then(r => {
      if (!r.ok) throw new Error('导出失败');
      return r.blob();
    }),

  // Social - Friends
  listFriends: () =>
    request('/api/social/friends'),
  requestFriend: (targetId: string, targetType: string) =>
    request('/api/social/friends/request', { method: 'POST', body: JSON.stringify({ target_id: targetId, target_type: targetType }) }),
  acceptFriend: (requestId: string) =>
    request(`/api/social/friends/${requestId}/accept`, { method: 'POST' }),
  rejectFriend: (requestId: string) =>
    request(`/api/social/friends/${requestId}/reject`, { method: 'POST' }),

  // Social - Hires (Agent hiring)
  listHires: () =>
    request('/api/social/hires'),
  hireAgent: (agentId: string, groupId: string) =>
    request('/api/social/hires', { method: 'POST', body: JSON.stringify({ agent_id: agentId, group_id: groupId }) }),

  // Social - Moments
  listMoments: (offset?: number, limit?: number) =>
    request(`/api/social/moments?offset=${offset || 0}&limit=${limit || 20}`),
  postMoment: (content: string, visibility?: string) =>
    request('/api/social/moments', { method: 'POST', body: JSON.stringify({ content, visibility: visibility || 'public' }) }),
  likeMoment: (momentId: string) =>
    request(`/api/social/moments/${momentId}/like`, { method: 'POST' }),
  commentMoment: (momentId: string, content: string) =>
    request(`/api/social/moments/${momentId}/comments`, { method: 'POST', body: JSON.stringify({ content }) }),

  // Templates
  listTemplates: () =>
    request('/api/templates/'),
  getTemplate: (id: string) =>
    request(`/api/templates/${id}`),
  createTemplate: (name: string, description: string, config: any) =>
    request('/api/templates/', { method: 'POST', body: JSON.stringify({ name, description, config }) }),
  createGroupFromTemplate: (templateId: string, ownerId: string) =>
    request(`/api/templates/${templateId}/create-group`, { method: 'POST', body: JSON.stringify({ owner_id: ownerId }) }),

  // Scheduled Tasks
  listScheduledTasks: () =>
    request('/api/scheduled-tasks/'),
  createScheduledTask: (name: string, cronExpression: string, timezone: string, actionType: string, actionConfig: any) =>
    request('/api/scheduled-tasks/', { method: 'POST', body: JSON.stringify({ name, cron_expression: cronExpression, timezone, action_type: actionType, action_config: actionConfig }) }),
  updateScheduledTask: (id: string, data: any) =>
    request(`/api/scheduled-tasks/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
  deleteScheduledTask: (id: string) =>
    request(`/api/scheduled-tasks/${id}`, { method: 'DELETE' }),

  // Workflow Templates
  getWorkflowTemplates: () =>
    request('/api/workflows/templates'),
  createWorkflowFromTemplate: (data: { template_id: string; name: string; owner_id: string; group_id?: string }) =>
    request('/api/workflows/create-from-template', { method: 'POST', body: JSON.stringify(data) }),

  // NL Cron
  parseCron: (naturalLanguage: string) =>
    request('/api/scheduled-tasks/parse-cron', { method: 'POST', body: JSON.stringify({ natural_language: naturalLanguage }) }),

  // Tasks (Session-based tasks)
  listTasks: (groupId?: string, status?: string) =>
    request(`/api/sessions/?${groupId ? 'group_id=' + groupId : ''}${status ? '&status=' + status : ''}`),
  createTask: (groupId: string, title: string, description: string, assignerType: string, assignerId: string, assigneeIds: string[], priority?: string) =>
    request('/api/sessions/', { method: 'POST', body: JSON.stringify({ group_id: groupId, title, description, assigner_type: assignerType, assigner_id: assignerId, assignee_ids: assigneeIds, priority: priority || 'normal' }) }),
  updateTask: (taskId: string, data: any) =>
    request(`/api/sessions/${taskId}`, { method: 'PUT', body: JSON.stringify(data) }),
  assignTask: (taskId: string, assigneeIds: string[]) =>
    request(`/api/sessions/${taskId}/assign`, { method: 'POST', body: JSON.stringify({ assignee_ids: assigneeIds }) }),
  completeTask: (taskId: string, result?: any, summary?: string) =>
    request(`/api/sessions/${taskId}/status`, { method: 'POST', body: JSON.stringify({ status: 'completed', result, summary }) }),
  reviewTask: (taskId: string, approved: boolean, comment?: string) =>
    request(`/api/sessions/${taskId}/review`, { method: 'POST', body: JSON.stringify({ approved, comment }) }),

  // Resources (Files with additional metadata)
  listResources: (groupId: string) =>
    request(`/api/files/?group_id=${groupId}`),
  listAccessibleResources: () =>
    request('/api/files/accessible'),
  createResource: (groupId: string, name: string, resourceType: string, metadata?: any) =>
    request('/api/resources/', { method: 'POST', body: JSON.stringify({ group_id: groupId, name, resource_type: resourceType, metadata }) }),

  // Reviews
  listReviews: (groupId?: string) =>
    request(`/api/reviews/?${groupId ? 'group_id=' + groupId : ''}`),
  listPendingReviews: () =>
    request('/api/reviews/pending-for-me'),

  // Parliament
  listParliaments: (groupId: string) =>
    request(`/api/parliaments/group/${groupId}`),
  getParliament: (id: string) =>
    request(`/api/parliaments/${id}`),
  createParliament: (data: { group_id: string; title: string; topic: string; consensus_type?: string; min_confidence?: number; max_rounds?: number }) =>
    request('/api/parliaments/', { method: 'POST', body: JSON.stringify(data) }),
  deliberateParliament: (id: string) =>
    request(`/api/parliaments/${id}/deliberate`, { method: 'POST' }),
  submitProposal: (parliamentId: string, proposerId: string, content: string, confidence?: number) =>
    request(`/api/parliaments/${parliamentId}/proposals`, { method: 'POST', body: JSON.stringify({ proposer_id: proposerId, content, confidence: confidence || 0.5 }) }),
  castVote: (parliamentId: string, proposalId: string, voterId: string, vote: string, confidence?: number, reasoning?: string) =>
    request(`/api/parliaments/${parliamentId}/votes`, { method: 'POST', body: JSON.stringify({ proposal_id: proposalId, voter_id: voterId, vote, confidence: confidence || 0.5, reasoning: reasoning || '' }) }),
  tallyParliament: (id: string) =>
    request(`/api/parliaments/${id}/tally`, { method: 'POST' }),
  escalateParliament: (id: string) =>
    request(`/api/parliaments/${id}/escalate`, { method: 'POST' }),
  resolveParliament: (id: string, resolution: any) =>
    request(`/api/parliaments/${id}/resolve`, { method: 'POST', body: JSON.stringify({ resolution }) }),

  // Hub (Skills marketplace / MCP tools)
  getHubStats: () =>
    request('/api/hub/stats'),
  getHubManifest: () =>
    request('/api/hub/manifest'),
};
