import type { ValidationStatus, Severity, GateStatus } from '../api/types';

type BadgeVariant = ValidationStatus | Severity | GateStatus;

export default function StatusBadge({ status }: { status: BadgeVariant }) {
  return <span className={`badge badge-${status}`}>{status}</span>;
}
