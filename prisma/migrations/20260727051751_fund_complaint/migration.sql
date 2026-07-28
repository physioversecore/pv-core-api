/*
  Warnings:

  - A unique constraint covering the columns `[refundId]` on the table `Complaint` will be added. If there are existing duplicate values, this will fail.
  - A unique constraint covering the columns `[complaintId]` on the table `Refund` will be added. If there are existing duplicate values, this will fail.

*/
-- CreateEnum
CREATE TYPE "CaseSource" AS ENUM ('PATIENT_SUBMITTED', 'THERAPIST_SUBMITTED', 'ADMIN_MANUAL');

-- AlterTable
ALTER TABLE "Complaint" ADD COLUMN     "refundId" TEXT,
ADD COLUMN     "source" "CaseSource" NOT NULL DEFAULT 'PATIENT_SUBMITTED';

-- AlterTable
ALTER TABLE "Refund" ADD COLUMN     "assigneeId" TEXT,
ADD COLUMN     "complaintId" TEXT,
ADD COLUMN     "notes" TEXT,
ADD COLUMN     "source" "CaseSource" NOT NULL DEFAULT 'PATIENT_SUBMITTED';

-- AlterTable
ALTER TABLE "Therapist" ADD COLUMN     "linkedComplaintsOverride" INTEGER,
ADD COLUMN     "reviewsOverride" INTEGER,
ADD COLUMN     "sessionsOverride" INTEGER,
ADD COLUMN     "statusOverride" TEXT,
ADD COLUMN     "trendOverride" DOUBLE PRECISION;

-- CreateTable
CREATE TABLE "PatientProfile" (
    "id" TEXT NOT NULL,
    "userId" TEXT NOT NULL,
    "name" TEXT NOT NULL,
    "phone" TEXT NOT NULL,
    "city" TEXT NOT NULL,
    "address" TEXT,
    "history" TEXT,
    "gender" TEXT NOT NULL DEFAULT 'Any',
    "notifEmail" BOOLEAN NOT NULL DEFAULT true,
    "notifSms" BOOLEAN NOT NULL DEFAULT false,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "PatientProfile_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "Verification" (
    "id" TEXT NOT NULL,
    "therapistId" TEXT NOT NULL,
    "documentType" TEXT NOT NULL,
    "uploaded" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "expires" TIMESTAMP(3),
    "status" TEXT NOT NULL DEFAULT 'Pending review',
    "severity" TEXT,
    "reportedBy" TEXT,
    "phone" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,
    "updatedAt" TIMESTAMP(3) NOT NULL,

    CONSTRAINT "Verification_pkey" PRIMARY KEY ("id")
);

-- CreateTable
CREATE TABLE "ActivityLog" (
    "id" TEXT NOT NULL,
    "adminId" TEXT NOT NULL,
    "action" TEXT NOT NULL,
    "targetType" TEXT NOT NULL,
    "targetId" TEXT NOT NULL,
    "metadata" JSONB,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "ActivityLog_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE UNIQUE INDEX "PatientProfile_userId_key" ON "PatientProfile"("userId");

-- CreateIndex
CREATE INDEX "PatientProfile_userId_idx" ON "PatientProfile"("userId");

-- CreateIndex
CREATE INDEX "Verification_therapistId_idx" ON "Verification"("therapistId");

-- CreateIndex
CREATE INDEX "Verification_status_idx" ON "Verification"("status");

-- CreateIndex
CREATE INDEX "Verification_therapistId_status_idx" ON "Verification"("therapistId", "status");

-- CreateIndex
CREATE INDEX "ActivityLog_adminId_idx" ON "ActivityLog"("adminId");

-- CreateIndex
CREATE INDEX "ActivityLog_targetType_targetId_idx" ON "ActivityLog"("targetType", "targetId");

-- CreateIndex
CREATE INDEX "ActivityLog_createdAt_idx" ON "ActivityLog"("createdAt");

-- CreateIndex
CREATE UNIQUE INDEX "Complaint_refundId_key" ON "Complaint"("refundId");

-- CreateIndex
CREATE UNIQUE INDEX "Refund_complaintId_key" ON "Refund"("complaintId");

-- CreateIndex
CREATE INDEX "Refund_assigneeId_idx" ON "Refund"("assigneeId");

-- AddForeignKey
ALTER TABLE "PatientProfile" ADD CONSTRAINT "PatientProfile_userId_fkey" FOREIGN KEY ("userId") REFERENCES "User"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Verification" ADD CONSTRAINT "Verification_therapistId_fkey" FOREIGN KEY ("therapistId") REFERENCES "Therapist"("id") ON DELETE CASCADE ON UPDATE CASCADE;

-- AddForeignKey
ALTER TABLE "Refund" ADD CONSTRAINT "Refund_complaintId_fkey" FOREIGN KEY ("complaintId") REFERENCES "Complaint"("id") ON DELETE SET NULL ON UPDATE CASCADE;
