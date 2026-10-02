"""Domain sandboxes for RecoverBench."""

from recoverbench.domains.cloud.cloud_sandbox import CloudResourceSandbox
from recoverbench.domains.crm.crm_sandbox import CRMSandbox, CRMSandbox as CRMLeadSandbox
from recoverbench.domains.database.sqlite_sandbox import SQLiteSandbox
from recoverbench.domains.git.git_sandbox import GitWorkspaceSandbox, GitWorkspaceSandbox as GitSandbox
from recoverbench.domains.messaging.messaging_sandbox import MessagingNotificationSandbox
from recoverbench.domains.payments.payment_sandbox import (
    DoubleEntryLedgerSandbox,
    PaymentGatewaySimulator,
)
from recoverbench.domains.storage.storage_sandbox import ObjectStorageSandbox
from recoverbench.domains.ticketing.ticketing_sandbox import (
    IncidentDeskSandbox,
    IncidentDeskSandbox as TicketingIncidentSandbox,
)

__all__ = [
    "CloudResourceSandbox",
    "CRMSandbox",
    "CRMLeadSandbox",
    "DoubleEntryLedgerSandbox",
    "GitSandbox",
    "GitWorkspaceSandbox",
    "IncidentDeskSandbox",
    "MessagingNotificationSandbox",
    "ObjectStorageSandbox",
    "PaymentGatewaySimulator",
    "SQLiteSandbox",
    "TicketingIncidentSandbox",
]
