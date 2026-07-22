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

-- CreateIndex
CREATE INDEX "AuditLogEntry_therapistId_idx" ON "AuditLogEntry"("therapistId");

-- CreateIndex
CREATE INDEX "AuditLogEntry_date_idx" ON "AuditLogEntry"("date");

-- CreateIndex
CREATE INDEX "CartItem_userId_idx" ON "CartItem"("userId");

-- CreateIndex
CREATE INDEX "Payment_userId_idx" ON "Payment"("userId");

-- CreateIndex
CREATE INDEX "Payment_sessionId_idx" ON "Payment"("sessionId");

-- CreateIndex
CREATE INDEX "Payment_status_idx" ON "Payment"("status");

-- CreateIndex
CREATE INDEX "Payment_userId_status_idx" ON "Payment"("userId", "status");

-- CreateIndex
CREATE INDEX "Report_patientId_idx" ON "Report"("patientId");

-- CreateIndex
CREATE INDEX "Report_therapistId_idx" ON "Report"("therapistId");

-- CreateIndex
CREATE INDEX "Report_sessionId_idx" ON "Report"("sessionId");

-- CreateIndex
CREATE INDEX "Review_patientId_idx" ON "Review"("patientId");

-- CreateIndex
CREATE INDEX "Review_therapistId_idx" ON "Review"("therapistId");

-- CreateIndex
CREATE INDEX "Review_patientId_therapistId_idx" ON "Review"("patientId", "therapistId");

-- CreateIndex
CREATE INDEX "ScheduleBlockRequest_therapistId_idx" ON "ScheduleBlockRequest"("therapistId");

-- CreateIndex
CREATE INDEX "ScheduleBlockRequest_status_idx" ON "ScheduleBlockRequest"("status");

-- CreateIndex
CREATE INDEX "ScheduleBlockRequest_therapistId_status_idx" ON "ScheduleBlockRequest"("therapistId", "status");

-- CreateIndex
CREATE INDEX "Session_patientId_idx" ON "Session"("patientId");

-- CreateIndex
CREATE INDEX "Session_therapistId_idx" ON "Session"("therapistId");

-- CreateIndex
CREATE INDEX "Session_status_idx" ON "Session"("status");

-- CreateIndex
CREATE INDEX "Session_date_idx" ON "Session"("date");

-- CreateIndex
CREATE INDEX "Session_patientId_status_idx" ON "Session"("patientId", "status");

-- CreateIndex
CREATE INDEX "Session_therapistId_status_idx" ON "Session"("therapistId", "status");

-- CreateIndex
CREATE INDEX "Session_therapistId_date_idx" ON "Session"("therapistId", "date");

-- CreateIndex
CREATE INDEX "Therapist_city_idx" ON "Therapist"("city");

-- CreateIndex
CREATE INDEX "Therapist_specialty_idx" ON "Therapist"("specialty");

-- CreateIndex
CREATE INDEX "Therapist_city_specialty_idx" ON "Therapist"("city", "specialty");

-- CreateIndex
CREATE INDEX "User_role_idx" ON "User"("role");

-- CreateIndex
CREATE INDEX "User_status_idx" ON "User"("status");

-- CreateIndex
CREATE INDEX "User_city_idx" ON "User"("city");

-- CreateIndex
CREATE INDEX "User_referralCode_idx" ON "User"("referralCode");

-- CreateIndex
CREATE INDEX "User_role_status_idx" ON "User"("role", "status");
