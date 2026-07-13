export type ProfileUserAccount = {
  id: number;
  email: string;
  display_name: string;
  role: string;
  timezone?: string;
  created_at?: string;
};

export type AuditEvent = {
  id: number;
  event_kind: string;
  title: string;
  body?: string | null;
  actor_display_name?: string | null;
  recipient_display_name?: string | null;
  character_name?: string | null;
  is_read: boolean;
  created_at?: string | null;
};

export type PrivateMessage = {
  id: number;
  sender_user_id: number;
  sender_display_name?: string | null;
  recipient_user_id: number;
  recipient_display_name?: string | null;
  subject: string;
  body: string;
  is_read: boolean;
  created_at?: string | null;
};

export type EveMailCharacter = {
  token_id: number;
  character_id: number;
  character_name: string;
  can_read: boolean;
  can_send: boolean;
  can_organize: boolean;
  missing_mail_scopes: string[];
};

export type EveMailRecipient = {
  recipient_id: number;
  recipient_type: string;
  name?: string | null;
};

export type EveMailHeader = {
  mail_id: number;
  subject?: string | null;
  from?: number | null;
  from_name?: string | null;
  recipients?: EveMailRecipient[];
  timestamp?: string | null;
  is_read?: boolean;
  labels?: number[];
};

export type EveMailMessage = EveMailHeader & {
  body?: string | null;
};

export type NotificationInbox = {
  unread_count: number;
  events: AuditEvent[];
  messages: PrivateMessage[];
  sent_messages?: PrivateMessage[];
  users: ProfileUserAccount[];
};

export type ProfileFocus = {
  section: "messages";
  replyTo?: PrivateMessage;
  nonce: number;
};

export type ProfileEsiAuthInfo = {
  ready: boolean;
  message?: string;
  url?: string;
  required_scopes: string[];
};
