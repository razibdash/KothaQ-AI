export type Organization = {
  id: string;
  name: string;
  slug: string;
};

export type CallLog = {
  id: string;
  organizationId: string;
  callerNumber?: string;
  status: string;
};
