# Extensions and security deposits

Start in **Allotments → View term history** for the allottee. Each row represents one recorded contract term.

## Raise and print an extension fee

1. Open **Details** on the preceding term. Under **One-off charges and receipts**, select **Assess extension fee**. Enter the approved assessment, tax, deadline, and reference.
2. Open the saved charge and select **Print extension fee demand**. The demand uses Invoice Format 2 and leaves the standard **Invoice Date** line blank for completion. You can also find it in **Bills** by searching for **Extension fee demand**.
3. Use **Record charge receipt** to record the payment. **Charge details** from the Bills list opens the original assessment and its receipt history. The same charge is shown in both places.
4. When the new term is recorded, BillTrack links the fee from the preceding term. Notice-based renewals require the assessed extension fee to be settled before a new renewal is recorded.

## Link a term entered as a separate award

A superuser opens the later term’s **Actions → Link as extension** and selects the preceding term. Enter the renewal approval reference, satisfactory performance reference, and reason for correcting the link. If the fee for this renewal was assessed on the later term, select **Use the existing fee on this term for this extension**. The linkage preserves invoice and receipt records and puts the later term’s rates on the original award’s schedule.

If the link is blocked, review whether both terms belong to the same allotment, their dates overlap, their recorded rent schedules conflict, or the later term has its own security history. See the [estate workflow](ESTATE-WORKFLOW.md#allotment-and-renewal) for term details.

## Calculate and review a security deposit

1. Open the original award’s **Details → Security deposit → Review security requirement** as a superuser. Enter the **initial monthly rent** and leave **Approved required deposit** blank to calculate it. BillTrack uses three months’ rent rounded up to the next ₹100. An exact multiple of ₹100 stays the same. For example, ₹2,850 × 3 = ₹8,550, which rounds up to ₹8,600.
2. Choose **Before allotment order** for the usual offer → deposit → final order sequence. Enter the offer date and deadline if known. When the deadline is blank, BillTrack uses the order date as the cutoff. **After allotment order** uses the order date plus seven days.
3. In **Approval / actual payment reference**, enter the offer, order, or other document that approves the deposit requirement. Enter the reason, choose **Preview security decision**, and confirm the reviewed amount. **Not reviewed** means there is no saved requirement yet.

## Record a receipt and carry the deposit forward

Use **Record deposit receipt** under the original award. Enter the actual amount, actual payment date, and voucher or DD reference. The date can precede the allotment order. Check **Currently held** and the movement history before entering a receipt.

When the allottee chooses to retain the deposit, open **Record renewal** or **Edit term** on the linked extension and select **Carry forward existing security deposit**. Once saved, the extension’s security section shows **Deposit carry-forward for this extension · Recorded**. The held amount remains on the original award’s ledger, so record the receipt once.

## Save an approved date exception

If the term starts before the allotment letter was issued or exceeds the allowed duration, saving opens **Record date exception**. Enter the approval reference and reason and select **Save with exception**. Cancel to revise the dates with the rest of your form intact. This prompt works with additional allotment details switched off.
