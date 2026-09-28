# RecoverBench Public Task Specifications

RecoverBench spans 36 base workflows across 8 operational enterprise domains:

| Domain | Task ID | Split | Baseline Description | Fault Boundary |
| :--- | :--- | :---: | :--- | :--- |
| **Cloud** | `RB-CLOUD-001` | VAL | Autoscaling Policy Update | PRE_MUTATION |
| **Cloud** | `RB-CLOUD-002` | DEV | VPC Subnet Route Table Association | POST_MUTATION_PRE_ACK |
| **Cloud** | `RB-CLOUD-003` | DEV | IAM Role Policy Attachment | POST_MUTATION_PRE_ACK |
| **Cloud** | `RB-CLOUD-004` | TEST | Blue-Green Service Deployment Cutover | POST_MUTATION_PRE_ACK |
| **CRM** | `RB-CRM-001` | VAL | Lead Conversion Pipeline Stage Update | PRE_MUTATION |
| **CRM** | `RB-CRM-002` | DEV | Contact Account Reassignment | POST_MUTATION_PRE_ACK |
| **CRM** | `RB-CRM-003` | DEV | Opportunity Deal Stage Transition | POST_MUTATION_PRE_ACK |
| **CRM** | `RB-CRM-004` | TEST | Enterprise SLA Tier Renewal | POST_MUTATION_PRE_ACK |
| **Database** | `RB-DB-001` | DEV | Customer Address Update | POST_MUTATION_PRE_ACK |
| **Database** | `RB-DB-002` | VAL | Order Status Transition | PRE_MUTATION |
| **Database** | `RB-DB-003` | DEV | Inventory Stock Level Decrement | POST_MUTATION_PRE_ACK |
| **Database** | `RB-DB-004` | TEST | Schema Migration with Batch Audit Log | POST_MUTATION_PRE_ACK |
| **Database** | `RB-DB-005` | TEST | Read-Modify-Write Bank Dividend Allocation | POST_MUTATION_PRE_ACK |
| **Git** | `RB-GIT-001` | DEV | Fast-Forward Branch Merge | POST_MUTATION_PRE_ACK |
| **Git** | `RB-GIT-002` | VAL | Commit Revert with Commit Message | PRE_MUTATION |
| **Git** | `RB-GIT-003` | DEV | Pull Request Approval and Squashed Merge | POST_MUTATION_PRE_ACK |
| **Git** | `RB-GIT-004` | TEST | Release Tag Cut and Cherry-Pick | POST_MUTATION_PRE_ACK |
| **Messaging**| `RB-MSG-001` | DEV | Direct Message Dispatch | POST_MUTATION_PRE_ACK |
| **Messaging**| `RB-MSG-002` | VAL | Channel Topic Configuration | PRE_MUTATION |
| **Messaging**| `RB-MSG-003` | DEV | Broadcast Channel Announcement | POST_MUTATION_PRE_ACK |
| **Messaging**| `RB-MSG-004` | TEST | High-Urgency Pager Callout with Delivery ACK | POST_MUTATION_PRE_ACK |
| **Messaging**| `RB-MSG-005` | TEST | Webhook Fanout with Delivery Confirmation | POST_MUTATION_PRE_ACK |
| **Payments** | `RB-PAY-001` | VAL | Customer Card Tokenization | PRE_MUTATION |
| **Payments** | `RB-PAY-002` | DEV | Invoice Payment Capture | POST_MUTATION_PRE_ACK |
| **Payments** | `RB-PAY-003` | DEV | Refund Authorization | POST_MUTATION_PRE_ACK |
| **Payments** | `RB-PAY-004` | TEST | Subscription Renewal with Grace Period | POST_MUTATION_PRE_ACK |
| **Payments** | `RB-PAY-005` | TEST | Multi-Currency Cross-Border Wire Transfer | POST_MUTATION_PRE_ACK |
| **Storage** | `RB-STOR-001` | DEV | File Upload with Hash Checksum | POST_MUTATION_PRE_ACK |
| **Storage** | `RB-STOR-002` | VAL | Object Lifecycle Policy Expiration | PRE_MUTATION |
| **Storage** | `RB-STOR-003` | VAL | Bucket CORS Configuration | PRE_MUTATION |
| **Storage** | `RB-STOR-004` | TEST | Cross-Bucket Object Replication | POST_MUTATION_PRE_ACK |
| **Storage** | `RB-STOR-005` | TEST | Atomic Object Swap with Cleanup | POST_MUTATION_PRE_ACK |
| **Ticketing**| `RB-TICK-001` | VAL | Ticket Priority Escalation | PRE_MUTATION |
| **Ticketing**| `RB-TICK-002` | DEV | Ticket Assignment with Assignee Notification | POST_MUTATION_PRE_ACK |
| **Ticketing**| `RB-TICK-003` | VAL | Incident Resolution with Root Cause Categorization | PRE_MUTATION |
| **Ticketing**| `RB-TICK-004` | TEST | SLA Escalation Policy Cascade | POST_MUTATION_PRE_ACK |
