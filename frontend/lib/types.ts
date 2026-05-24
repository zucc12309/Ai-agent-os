export interface LiveRecord {
  status: string;
  app_name: string;
  environment: string;
  mcp_path: string;
}

export interface ReadinessRecord extends LiveRecord {
  database: string;
  agent_count: number;
  tool_count: number;
  approval_count: number;
  audit_log_count: number;
}

export interface AuthSessionRecord {
  authenticated: boolean;
  agent_id: string;
  agent_name: string;
  api_key_prefix: string;
  is_admin: boolean;
  enabled: boolean;
  session_expires_at: string;
}

export interface ToolRecord {
  id: string;
  tool_name: string;
  description: string;
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  connector_type: string;
  risk_level: string;
  requires_approval: boolean;
  enabled: boolean;
  is_write: boolean;
  created_at: string;
  updated_at: string;
}

export interface AgentRecord {
  id: string;
  name: string;
  description: string | null;
  api_key_prefix: string;
  enabled: boolean;
  is_admin: boolean;
  allowed_tool_names: string[];
  approvable_tool_names: string[];
  created_at: string;
  last_used_at: string | null;
}

export interface ApprovalRecord {
  id: string;
  agent_id: string;
  tool_id: string;
  decided_by_agent_id: string | null;
  tool_name: string;
  input_payload: Record<string, unknown>;
  approval_status: string;
  execution_status: string;
  decision_reason: string | null;
  requested_at: string;
  decided_at: string | null;
  executed_at: string | null;
  execution_output_payload: Record<string, unknown> | null;
  execution_error_message: string | null;
  created_at: string;
  updated_at: string;
}

export interface AuditLogRecord {
  id: string;
  agent_id: string;
  tool_id: string | null;
  tool_name: string;
  input_payload: Record<string, unknown>;
  output_payload: Record<string, unknown> | null;
  status: string;
  error_message: string | null;
  approval_status: string;
  execution_time_ms: number;
  event_hash: string | null;
  previous_event_hash: string | null;
  created_at: string;
}
