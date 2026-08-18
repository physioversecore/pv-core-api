-- CreateEnum
CREATE TYPE "ApplicationStatus" AS ENUM ('INCOMPLETE', 'SUBMITTED', 'CHANGES_REQUIRED', 'APPROVED', 'REJECTED');

-- AlterTable
ALTER TABLE "PatientProfile" ADD COLUMN     "onboardingCompleted" BOOLEAN NOT NULL DEFAULT false,
ADD COLUMN     "onboardingStep" TEXT;

-- AlterTable
ALTER TABLE "Therapist" ADD COLUMN     "applicationStatus" "ApplicationStatus" NOT NULL DEFAULT 'INCOMPLETE';

-- CreateTable
CREATE TABLE "TherapistApplicationFeedback" (
    "id" TEXT NOT NULL,
    "therapistId" TEXT NOT NULL,
    "section" TEXT NOT NULL,
    "message" TEXT NOT NULL,
    "adminId" TEXT,
    "createdAt" TIMESTAMP(3) NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT "TherapistApplicationFeedback_pkey" PRIMARY KEY ("id")
);

-- CreateIndex
CREATE INDEX "TherapistApplicationFeedback_therapistId_idx" ON "TherapistApplicationFeedback"("therapistId");

-- AddForeignKey
ALTER TABLE "TherapistApplicationFeedback" ADD CONSTRAINT "TherapistApplicationFeedback_therapistId_fkey" FOREIGN KEY ("therapistId") REFERENCES "Therapist"("id") ON DELETE CASCADE ON UPDATE CASCADE;
