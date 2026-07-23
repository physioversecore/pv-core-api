-- CreateTable
CREATE TABLE "Complaint" (
    "id" TEXT NOT NULL,
    "type" TEXT NOT NULL,
    "complainantId" TEXT NOT NULL,
    "complainantName" TEXT NOT NULL,
    "againstId" TEXT NOT NULL,
    "againstName" TEXT NOT NULL,
    "category" TEXT NOT NULL,
    "priority" TEXT NOT NULL DEFAULT 'Normal',
    "status" TEXT NOT NULL DEFAULT 'Open',
    "description" TEXT NOT NULL,
    "bookingId" TEXT,
    "evidenceUrls" TEXT,
    "preferredOutcome" TEXT,
    "assignee" TEXT,
    "adminNotes" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Complaint_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "Complaint_complainantId_idx" ON "Complaint"("complainantId");

-- CreateIndex
CREATE INDEX "Complaint_againstId_idx" ON "Complaint"("againstId");

-- CreateIndex
CREATE INDEX "Complaint_status_idx" ON "Complaint"("status");

-- CreateIndex
CREATE INDEX "Complaint_type_idx" ON "Complaint"("type");

-- CreateIndex
CREATE INDEX "Complaint_type_status_idx" ON "Complaint"("type", "status");
